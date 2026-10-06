import asyncio
import copy
from fastapi import HTTPException
from pydantic import ValidationError
from app.config import get_settings
from app.schemas.domain import RunInput, Clarification, AddOffer, uid
from app.services.investigation.runner import Investigation, initial_state
from app.services.serpapi.client import SerpApiClient

class MemoryStore:
    def __init__(self): self.runs={}
    def save(self,state): self.runs[state["run_id"]]=copy.deepcopy(state)
    def get(self,run_id): return copy.deepcopy(self.runs.get(run_id))
    def recover(self): pass

def public_state(state):
    result=copy.deepcopy(state)
    for source in result["sources"]:
        source.pop("text",None)
    return result

class RunManager:
    def __init__(self,settings_provider=get_settings,store=None,cache=None):
        self.settings_provider=settings_provider
        self.store=store or MemoryStore()
        self.cache=cache
        self.tasks={}

    def get(self,run_id):
        state=self.store.get(run_id)
        if state is None:
            raise HTTPException(404,"Investigation not found.")
        task=self.tasks.get(run_id)
        if task and not task.done() and state['status']!='investigating':
            state['status']='investigating'
        return state

    def ensure_idle(self,run_id):
        task=self.tasks.get(run_id)
        if task and not task.done():
            raise HTTPException(409,"This investigation is still running.")
        if sum(not task.done() for task in self.tasks.values())>=2:
            raise HTTPException(429,"Two investigations are already running. Please wait.")

    def start(self,state):
        self.ensure_idle(state["run_id"])
        settings=self.settings_provider()
        if state["input"]["mode"]=="live" and not settings.readiness()["live_ready"]:
            raise HTTPException(503,{"message":"Live providers need backend configuration.","missing":settings.readiness()["missing"]})
        if state["input"]["mode"]=="replay" and not settings.enable_replay:
            raise HTTPException(400,"Recorded evidence mode is disabled.")
        state["status"]="investigating"
        self.store.save(state)
        runner=Investigation(state,settings,sink=self.store.save,search=SerpApiClient(settings,cache=self.cache))
        self.tasks[state["run_id"]]=asyncio.create_task(runner.execute())
        return {"run_id":state["run_id"],"status":"investigating"}

    def create(self,inputs):
        return self.start(initial_state(uid("run"),inputs,self.settings_provider()))

    async def clarify(self,run_id,payload: Clarification):
        self.ensure_idle(run_id)
        state=self.get(run_id)
        try:
            inputs=RunInput.model_validate({**state["input"],**payload.model_dump(exclude_unset=True)})
        except ValidationError:
            raise HTTPException(422,"Configuration contains invalid module capacities or model details.") from None
        if inputs.device_model!=state["input"]["device_model"]:
            return self.create(inputs)
        state["input"]=inputs.model_dump()
        if state["status"]=="awaiting_clarification":
            return self.start(state)
        runner=Investigation(state,self.settings_provider(),sink=self.store.save)
        runner.emit("checks","Configuration updated from your clarification; rechecking stored evidence")
        await runner.checks({})
        await runner.report({})
        return {"run_id":run_id,"status":state["status"]}

    def add_offer(self,run_id,payload: AddOffer):
        self.ensure_idle(run_id)
        state=self.get(run_id)
        if len(payload.part_number.strip()) < 3:
            raise HTTPException(422,"Enter an exact manufacturer part number.")
        if len(state["offers"])>=self.settings_provider().max_offers:
            raise HTTPException(400,"Candidate limit reached. Start a new investigation.")
        state["input"]["part_number"]=payload.part_number.strip()
        return self.start(state)

    async def shutdown(self):
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks.values(),return_exceptions=True)

def markdown_report(state):
    lines=["# FitProof — evidence report","",f"Mode: **{state['mode']}**. Status: {state['status']}.",
      f"Device: {state['input']['device_model']}",f"Run: {state['run_id']}; updated {state['updated_at']}.",
      "","Only documented checks are assessed. No installation guarantee is provided.",""]
    if state["mode"]=="replay":
        lines += ["Recorded manufacturer excerpts and human-reviewed extraction fixtures; no live search or AI call.",""]
    for offer in state["offers"]:
        lines += [f"## {offer['part_number'] or offer['title']}",offer["result"].replace("_"," ").title(),""]
        for check in state["checks"]:
            if check["offer_id"]!=offer["id"]:
                continue
            lines.append(f"- {check['label']}: **{check['status']}** — {check['explanation']}")
            for fact in state["facts"]:
                if fact["id"] in check["fact_ids"]:
                    src=next((s for s in state["sources"] if s["id"]==fact["source_id"]),None)
                    if src:
                        lines.append(f"  - {fact['evidence_span']} ([{src['publisher']}]({src['url']}), retrieved {src['retrieved_at']})")
        lines.append("")
    return "\n".join(lines)
