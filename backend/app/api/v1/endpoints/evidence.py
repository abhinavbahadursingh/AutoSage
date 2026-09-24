"""Evidence-trail endpoints (Phase 2: auth + workspace isolation).

The verification DAG assembly lands in later phases; this route already
enforces that only the owning user can read a run's evidence trail.
"""
from fastapi import APIRouter

from app.api.deps import OwnedRun

router = APIRouter()


@router.get("", summary="Get the evidence trail for my run")
@router.get("/", include_in_schema=False)
async def get_evidence_trail(run: OwnedRun) -> dict:
    return {"run_id": str(run.id), "nodes": [], "edges": []}
