import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import httpx
from app.config import Settings
from app.services.errors import ServiceError


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SerpApiClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None, cache=None):
        self.settings = settings
        self.http = http
        self.cache = cache
        self.requests_used = 0
        self.records: list[dict] = []

    async def search(self, query: str, engine: str = "google", country: str = "IN") -> dict[str, Any]:
        if engine not in {"google", "google_shopping_light"}:
            raise ServiceError("invalid_engine", "Unsupported search engine.")
        if not self.settings.serpapi_key.get_secret_value():
            raise ServiceError("configuration", "Configure SERPAPI_KEY on the backend to run live searches.")
        params = {"q": query[:500], "engine": engine, "gl": country.lower(), "hl": "en"}
        cached = self.cache.get(params) if self.cache else None
        record = {
            "id": "search_" + uuid4().hex,
            "query": params["q"],
            "engine": engine,
            "country": country,
            "created_at": now(),
            "origin": "cache" if cached else "live",
            "request_count": 0,
            "status": "pending",
            "response_id": None,
        }
        self.records.append(record)
        if cached is not None:
            record.update(status="success", response_id=cached.get("search_metadata", {}).get("id"))
            return cached
        owned = self.http is None
        client = self.http or httpx.AsyncClient(timeout=self.settings.request_timeout)
        try:
            for attempt in range(3):
                if self.requests_used >= self.settings.max_searches:
                    record["status"] = "budget_exhausted"
                    raise ServiceError(
                        "budget", "Investigation search limit reached; some checks remain unresolved."
                    )
                self.requests_used += 1
                record["request_count"] += 1
                try:
                    response = await client.get(
                        "https://serpapi.com/search",
                        params={**params, "api_key": self.settings.serpapi_key.get_secret_value()},
                    )
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt < 2:
                        await asyncio.sleep(0.25 * (attempt + 1))
                        continue
                    raise ServiceError(
                        "search_timeout", "Search timed out. Available evidence is preserved."
                    ) from None
                if response.status_code in (401, 403):
                    raise ServiceError(
                        "search_auth", "SerpApi rejected the API key. Check backend configuration."
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < 2:
                        await asyncio.sleep(0.25 * (attempt + 1))
                        continue
                    raise ServiceError(
                        "search_unavailable", "Search quota or provider availability prevented this request."
                    )
                if response.status_code != 200:
                    raise ServiceError("search_failed", "Search provider could not complete this request.")
                try:
                    raw = response.json()
                except ValueError:
                    raise ServiceError("search_format", "Search returned an unreadable response.") from None
                if not isinstance(raw, dict) or raw.get("error"):
                    raise ServiceError(
                        "search_failed", "Search provider returned an error. Check account quota and query."
                    )
                # Persist only needed fields; raw provider URLs can contain a key.
                data = {
                    "search_metadata": {
                        k: raw.get("search_metadata", {}).get(k) for k in ("id", "status", "created_at")
                    },
                    "organic_results": raw.get("organic_results", []),
                    "shopping_results": raw.get("shopping_results", []),
                    "categorized_shopping_results": raw.get("categorized_shopping_results", []),
                }
                data = scrub_secrets(data, self.settings.serpapi_key.get_secret_value())
                record.update(status="success", response_id=data["search_metadata"]["id"])
                if self.cache:
                    self.cache.set(params, data)
                return data
            raise ServiceError("search_failed", "Search could not complete.")
        except ServiceError:
            if record["status"] == "pending":
                record["status"] = "failed"
            raise
        finally:
            if owned:
                await client.aclose()


def scrub_secrets(value, key: str):
    if isinstance(value, dict):
        return {
            k: scrub_secrets(v, key)
            for k, v in value.items()
            if k not in {"api_key", "serpapi_link", "serpapi_product_api", "serpapi_immersive_product_api"}
        }
    if isinstance(value, list):
        return [scrub_secrets(v, key) for v in value]
    if isinstance(value, str) and key:
        return value.replace(key, "[redacted]")
    return value
