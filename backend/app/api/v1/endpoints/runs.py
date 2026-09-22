from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/")
async def launch_run(project_id: str):
    return {"run_id": "run-placeholder", "status": "PENDING"}

@router.get("/{run_id}/stream")
async def stream_run_logs(run_id: str):
    async def event_generator():
        yield "data: {\"event\": \"connected\", \"run_id\": \"run-placeholder\"}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
