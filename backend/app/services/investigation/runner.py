import asyncio
import re
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.config import Settings
from app.schemas.domain import RunInput, Source, Fact, Offer, utcnow
from app.services.serpapi.client import SerpApiClient
from app.services.evidence.sources import source_from_result, fetch_source, MANUFACTURERS
from app.services.evidence.validation import validate_fact, identity_key
from app.services.extraction.llm import LLMExtractor
from app.services.extraction.replay import ReplayExtractor, replay_sources
from app.services.compatibility.engine import evaluate
from app.services.errors import ServiceError


class GraphState(TypedDict):
    state: dict


def initial_state(run_id: str, inputs: RunInput, settings: Settings) -> dict:
    return {
        "run_id": run_id,
        "input": inputs.model_dump(),
        "status": "investigating",
        "stage": "validate",
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "sources": [],
        "facts": [],
        "offers": [],
        "checks": [],
        "searches": [],
        "queries_used": 0,
        "max_searches": settings.max_searches,
        "followup_rounds": 0,
        "max_followup_rounds": settings.max_followup_rounds,
        "events": [],
        "missing_fields": [],
        "errors": [],
        "summary": "",
        "mode": inputs.mode,
    }


def possible_sku(title: str) -> str | None:
    patterns = [r"\b(?:KCP|KVR)[A-Z0-9]+/[0-9]{1,3}\b", r"\bCT[A-Z0-9]{7,}\b", r"\bCMSX[A-Z0-9]{6,}\b"]
    for pattern in patterns:
        match = re.search(pattern, title, re.I)
        if match:
            return match.group().upper()
    return None


def domain_for(subject: str) -> str | None:
    s = subject.lower()
    if s.startswith(("kcp", "kvr")):
        return "kingston.com"
    if s.startswith("ct") and any(c.isdigit() for c in s):
        return "crucial.com"
    for domain, brand in MANUFACTURERS.items():
        if brand.lower() in s:
            return domain
    return None


class Investigation:
    def __init__(self, state: dict, settings: Settings, sink=None, search=None, extractor=None, fetcher=None):
        self.state = state
        self.settings = settings
        self.inputs = RunInput.model_validate(state["input"])
        self.search = search or SerpApiClient(settings)
        self.search.requests_used = state["queries_used"]
        self.search.records = list(state["searches"])
        self.extractor = extractor or (
            ReplayExtractor() if self.inputs.mode == "replay" else LLMExtractor(settings)
        )
        self.fetcher = fetcher or fetch_source
        self.sink = sink
        self.halted = False

    def emit(self, stage: str, message: str, kind="progress"):
        self.state.update(
            stage=stage,
            updated_at=utcnow(),
            queries_used=self.search.requests_used,
            searches=self.search.records,
        )
        self.state["events"].append(
            {
                "id": len(self.state["events"]) + 1,
                "event_type": kind,
                "stage": stage,
                "message": message,
                "created_at": utcnow(),
            }
        )
        if self.sink:
            self.sink(self.state)

    def error(self, error: ServiceError):
        entry = {"code": error.code, "message": error.message}
        if entry not in self.state["errors"]:
            self.state["errors"].append(entry)
        if error.code in {"search_auth", "configuration", "search_unavailable", "budget"}:
            self.halted = True
        self.emit(self.state["stage"], error.message, "warning")

    async def query(self, q, engine="google"):
        if self.halted:
            return {}
        self.emit(
            self.state["stage"],
            "Searching manufacturer evidence" if engine == "google" else "Discovering current RAM offers",
        )
        try:
            result = await self.search.search(q, engine, self.inputs.country)
            self.emit(self.state["stage"], "Search response received")
            return result
        except ServiceError as error:
            self.error(error)
            return {}

    async def read_and_extract(self, source: Source, subject: str, kind: str):
        old = next((s for s in self.state["sources"] if s["url"] == source.url), None)
        if old:
            source = Source.model_validate(old)
        else:
            if len(self.state["sources"]) >= 18:
                return
            if self.inputs.mode != "replay":
                source = await self.fetcher(source)
            self.state["sources"].append(source.model_dump())
            self.emit(
                self.state["stage"],
                f"{source.publisher} source "
                + ("loaded" if source.fetch_status == "available" else "unavailable"),
            )
        if source.fetch_status != "available":
            return
        if any(
            f["source_id"] == source.id and identity_key(f["subject"]) == identity_key(subject)
            for f in self.state["facts"]
        ):
            return
        try:
            extraction = await self.extractor.extract(source, subject, kind, self.inputs.device_model)
            for draft in extraction.facts:
                fact = validate_fact(draft, source, subject, self.inputs.device_model)
                self.state["facts"].append(fact.model_dump())
            self.emit(
                self.state["stage"], f"{len(extraction.facts)} extracted facts checked against source text"
            )
        except ServiceError as error:
            self.error(error)

    async def search_documents(self, subject, kind, query=None):
        domain = domain_for(subject)
        q = (
            query
            or f'{("site:" + domain + " ") if domain else ""}"{subject}" {"memory specifications" if kind == "device" else "specification datasheet"}'
        )
        results = await self.query(q)
        count = 0
        for item in results.get("organic_results", []):
            source = source_from_result(item, self.search.records[-1]["id"] if self.search.records else None)
            if not source or source.source_type != "manufacturer":
                continue
            await self.read_and_extract(source, subject, kind)
            count += 1
            if count >= 2:
                break

    async def validate(self, _):
        self.emit("validate", "Checking the exact laptop and supplied configuration")
        if self.inputs.mode == "replay":
            if identity_key(self.inputs.device_model) != identity_key("Lenovo ThinkPad T480"):
                self.state["status"] = "awaiting_clarification"
                self.emit(
                    "validate",
                    "Recorded evidence covers Lenovo ThinkPad T480 only. Use live mode for another model.",
                    "warning",
                )
        elif not re.search(r"\d", self.inputs.device_model) or " or " in self.inputs.device_model.lower():
            self.state["status"] = "awaiting_clarification"
            self.emit(
                "validate", "Enter one exact laptop model, including its model code or suffix.", "warning"
            )
        return {"state": self.state}

    async def device(self, _):
        self.emit("device", "Resolving the exact laptop from manufacturer documentation")
        if self.inputs.mode == "replay":
            await self.read_and_extract(replay_sources()[0], self.inputs.device_model, "device")
        elif not any(
            f["field"] == "identity"
            and f["status"] == "supported"
            and identity_key(f["subject"]) == identity_key(self.inputs.device_model)
            for f in self.state["facts"]
        ):
            await self.search_documents(self.inputs.device_model, "device")
        return {"state": self.state}

    async def discover(self, _):
        self.emit("discover", "Preparing exact-part candidates")
        if self.inputs.part_number:
            if not any(o["part_number"] == self.inputs.part_number for o in self.state["offers"]):
                self.state["offers"].append(
                    Offer(
                        title=self.inputs.part_number, part_number=self.inputs.part_number, origin="user"
                    ).model_dump()
                )
        elif not self.state["offers"]:
            if self.inputs.mode == "replay":
                self.state["offers"] = [
                    Offer(
                        title="Kingston 16GB DDR4 SO-DIMM",
                        part_number="KCP432SD8/16",
                        manufacturer="Kingston",
                        origin="replay",
                    ).model_dump(),
                    Offer(
                        title="Kingston 16GB DDR4 desktop DIMM",
                        part_number="KVR32N22S8/16",
                        manufacturer="Kingston",
                        origin="replay",
                    ).model_dump(),
                    Offer(title="Generic 16GB DDR4 listing — identity example", origin="replay").model_dump(),
                ]
                self.emit("discover", "Three labelled example candidates loaded; no live prices or searches")
            else:
                known = {
                    f["field"]: f["value"]
                    for f in self.state["facts"]
                    if f["status"] == "supported" and f["subject"] == self.inputs.device_model
                }
                query = f"{self.inputs.desired_capacity_gb}GB {known.get('memory_generation', '')} {known.get('memory_form_factor', '')} RAM {self.inputs.device_model}"
                results = await self.query(query, "google_shopping_light")
                items = list(results.get("shopping_results", []))
                for group in results.get("categorized_shopping_results", []):
                    items.extend(group.get("shopping_results", []))
                seen = set()
                for item in items:
                    title = str(item.get("title", ""))
                    url = item.get("product_link")
                    signature = (title, url)
                    if not title or signature in seen:
                        continue
                    seen.add(signature)
                    price = item.get("price")
                    currency = "INR" if isinstance(price, str) and ("₹" in price or "INR" in price) else None
                    self.state["offers"].append(
                        Offer(
                            title=title,
                            part_number=possible_sku(title),
                            price=str(price) if price else None,
                            currency=currency,
                            seller=item.get("source"),
                            url=url,
                            origin=self.search.records[-1]["origin"],
                        ).model_dump()
                    )
                    if len(self.state["offers"]) >= self.settings.max_offers:
                        break
                if not self.state["offers"]:
                    self.emit(
                        "discover",
                        "No usable offers found. You can add an exact manufacturer part number.",
                        "warning",
                    )
        return {"state": self.state}

    async def parts(self, _):
        self.emit("parts", "Resolving exact RAM specifications")
        for raw in self.state["offers"]:
            part = raw.get("part_number")
            if not part:
                continue
            if self.inputs.mode == "replay":
                sources = replay_sources()
                match = next((s for s in sources[1:] if part.lower() in s.text.lower()), None)
                if match:
                    await self.read_and_extract(match, part, "part")
            else:
                await self.search_documents(part, "part")
        return {"state": self.state}

    async def audit(self, _):
        self.emit("audit", "Checking evidence coverage and missing fields")
        facts = [Fact.model_validate(f) for f in self.state["facts"]]
        gaps = []
        required = {
            "identity",
            "memory_generation",
            "memory_form_factor",
            "maximum_capacity_gb",
            "memory_slots",
        }
        existing = {
            f.field
            for f in facts
            if f.status == "supported" and identity_key(f.subject) == identity_key(self.inputs.device_model)
        }
        if required - existing:
            gaps.append(
                {"subject": self.inputs.device_model, "kind": "device", "fields": sorted(required - existing)}
            )
        for offer in self.state["offers"]:
            if not offer.get("part_number"):
                continue
            needed = {"identity", "memory_generation", "memory_form_factor", "module_capacity_gb"}
            have = {
                f.field
                for f in facts
                if f.status == "supported" and identity_key(f.subject) == identity_key(offer["part_number"])
            }
            if needed - have:
                gaps.append(
                    {"subject": offer["part_number"], "kind": "part", "fields": sorted(needed - have)}
                )
        self.state["missing_fields"] = gaps
        return {"state": self.state}

    def route_missing(self, _):
        if (
            self.state["missing_fields"]
            and self.inputs.mode == "live"
            and not self.halted
            and self.state["followup_rounds"] < self.settings.max_followup_rounds
            and self.search.requests_used < self.settings.max_searches
        ):
            return "followup"
        return "checks"

    async def followup(self, _):
        self.state["followup_rounds"] += 1
        self.emit("followup", "Looking for specific missing manufacturer facts")
        for gap in self.state["missing_fields"][:2]:
            try:
                q = await self.extractor.followup(gap["subject"], gap["fields"], domain_for(gap["subject"]))
                await self.search_documents(gap["subject"], gap["kind"], q)
            except ServiceError as error:
                self.error(error)
        return {"state": self.state}

    async def checks(self, _):
        self.emit("checks", "Running deterministic compatibility checks")
        facts = [Fact.model_validate(f) for f in self.state["facts"]]
        offers = []
        checks = []
        for raw in self.state["offers"]:
            offer, result = evaluate(self.inputs, Offer.model_validate(raw), facts)
            offers.append(offer.model_dump())
            checks.extend(c.model_dump() for c in result)
        self.state["offers"] = offers
        self.state["checks"] = checks
        return {"state": self.state}

    async def report(self, _):
        self.state["status"] = "completed"
        count = len(self.state["offers"])
        self.state["summary"] = (
            f"{count} candidate{'s' if count != 1 else ''} investigated. Each result reflects only the documented checks and your supplied configuration."
        )
        if not count:
            self.state["summary"] = (
                "No candidates were established. Add an exact RAM part number to continue."
            )
        self.emit("complete", "Investigation complete; unresolved checks remain visible", "completed")
        return {"state": self.state}

    def graph(self):
        graph = StateGraph(GraphState)
        for name in ("validate", "device", "discover", "parts", "audit", "followup", "checks", "report"):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "validate")
        graph.add_conditional_edges(
            "validate", lambda _: END if self.state["status"] == "awaiting_clarification" else "device"
        )
        for left, right in (
            ("device", "discover"),
            ("discover", "parts"),
            ("parts", "audit"),
            ("followup", "audit"),
            ("checks", "report"),
            ("report", END),
        ):
            graph.add_edge(left, right)
        graph.add_conditional_edges("audit", self.route_missing)
        return graph.compile()

    async def execute(self):
        try:
            async with asyncio.timeout(self.settings.run_timeout):
                await self.graph().ainvoke({"state": self.state}, {"recursion_limit": 35})
        except TimeoutError:
            self.error(
                ServiceError(
                    "run_timeout", "Investigation time limit reached. Partial evidence is preserved."
                )
            )
            await self.checks({})
            await self.report({})
        except asyncio.CancelledError:
            self.state["status"] = "interrupted"
            self.emit("interrupted", "Investigation interrupted; stored evidence is preserved.", "warning")
            raise
        except Exception:
            self.state["status"] = "failed"
            self.emit(
                "failed",
                "Investigation could not finish. No unsupported compatibility conclusion was generated.",
                "error",
            )
        return self.state
