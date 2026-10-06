import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, Response
from app.schemas.domain import RunInput, Clarification, AddOffer
from app.services.investigation.manager import public_state,markdown_report
router=APIRouter(prefix="/api/runs",tags=["investigations"])

@router.post("",status_code=202)
async def create_run(payload: RunInput,request: Request):
    return request.app.state.manager.create(payload)

@router.get("/{run_id}")
async def get_run(run_id: str,request: Request):
    return public_state(request.app.state.manager.get(run_id))

@router.post("/{run_id}/clarifications")
async def clarify(run_id: str,payload: Clarification,request: Request):
    return await request.app.state.manager.clarify(run_id,payload)

@router.post("/{run_id}/offers",status_code=202)
async def add_offer(run_id: str,payload: AddOffer,request: Request):
    return request.app.state.manager.add_offer(run_id,payload)

@router.get("/{run_id}/report")
async def report(run_id: str,request: Request):
    state=request.app.state.manager.get(run_id)
    return Response(markdown_report(state),media_type="text/markdown",headers={"Content-Disposition":f'attachment; filename="fitproof-{run_id}.md"'})

@router.get("/{run_id}/events")
async def events(run_id: str,request: Request,after: int=0):
    manager=request.app.state.manager
    manager.get(run_id)
    try:
        last=max(after,int(request.headers.get("last-event-id","0")))
    except ValueError:
        last=after
    async def stream():
        nonlocal last
        heartbeat=0
        while not await request.is_disconnected():
            state=manager.get(run_id)
            for event in state["events"]:
                if event["id"]>last:
                    last=event["id"]
                    yield f"id: {last}\nevent: update\ndata: {json.dumps(event)}\n\n"
            if state["status"]!="investigating":
                yield f"event: done\ndata: {json.dumps({'status':state['status']})}\n\n"
                break
            heartbeat+=1
            if heartbeat%30==0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(.25)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
