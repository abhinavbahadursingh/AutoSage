"""Pipeline-run endpoints (Phase 2: auth + workspace isolation).

Run orchestration, execution, and live streaming land in later phases; these
routes already enforce that only the owning user can launch or observe runs.
"""
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession, OwnedProject
from app.core.exceptions import NotFoundError
from app.models.run import PipelineRun

router = APIRouter()


@router.post("/", summary="Launch a run in my project")
async def launch_run(project: OwnedProject) -> dict:
    return {"project_id": str(project.id), "run_id": "run-placeholder", "status": "PENDING"}


@router.get("/{run_id}/stream", summary="Stream run events (placeholder)")
async def stream_run_logs(project: OwnedProject, run_id: UUID, session: DbSession) -> StreamingResponse:
    run = await session.get(PipelineRun, run_id)
    if run is None or run.project_id != project.id:
        # 404 (not 403): do not reveal whether the run exists.
        raise NotFoundError(f"Run {run_id} not found")

    async def event_generator():  # type: ignore[no-untyped-def]
        yield f'data: {{"event": "connected", "run_id": "{run_id}"}}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")
