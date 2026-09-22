from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def list_projects():
    return []

@router.post("/")
async def create_project():
    return {"id": "proj-placeholder", "name": "New Project"}
