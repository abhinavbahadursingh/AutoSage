from fastapi import APIRouter
router = APIRouter()

@router.get("/search")
async def search_memory(query: str):
    return {"results": []}
