"""API v1 Main Router."""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, projects, datasets, runs, evidence, memory

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(datasets.router, prefix="/projects/{project_id}/datasets", tags=["Datasets"])
api_router.include_router(runs.router, prefix="/projects/{project_id}/runs", tags=["Runs"])
api_router.include_router(evidence.router, prefix="/runs/{run_id}/evidence", tags=["Evidence"])
api_router.include_router(memory.router, prefix="/memory", tags=["Memory"])
