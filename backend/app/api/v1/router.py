"""API v1 Main Router."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, health, projects, datasets, runs, evidence,
    memory, experiments, workspaces, verification, storage, reproducibility,
    websocket,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_router.include_router(experiments.router, prefix="/experiments", tags=["Experiments"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(datasets.router, prefix="/projects/{project_id}/datasets", tags=["Datasets"])
api_router.include_router(runs.router, prefix="/projects/{project_id}/runs", tags=["Runs"])
api_router.include_router(evidence.router, prefix="/runs/{run_id}/evidence", tags=["Evidence"])
api_router.include_router(memory.router, prefix="/memory", tags=["Memory"])
api_router.include_router(verification.router, tags=["Verification"])
api_router.include_router(storage.router, prefix="/storage", tags=["Storage"])
api_router.include_router(reproducibility.router, tags=["Reproducibility"])
api_router.include_router(websocket.router, tags=["WebSocket"])
