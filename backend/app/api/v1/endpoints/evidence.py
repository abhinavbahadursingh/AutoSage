from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def get_evidence_trail(run_id: str):
    return {"nodes": [], "edges": []}
