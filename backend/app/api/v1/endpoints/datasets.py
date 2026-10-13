"""Dataset endpoints (Phase 2: auth + workspace isolation + security hardening).

Project-scoped routes live under ``/projects/{project_id}/datasets`` and keep
the original placeholder behaviour.

Two additional routes are mounted at the top level (``/datasets``) because
they must be reachable *without* a project in hand — the new-experiment form
checks a dataset before any project exists:

    GET  /datasets/resolve      is this filename resolvable for me?
    POST /datasets/upload       store a file so it becomes resolvable

Both share the worker's resolution rules (see
:mod:`app.services.dataset_service`) so the UI and the pipeline agree on what
"the dataset exists" means.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession, OwnedProject
from app.core.config import settings
from app.core.file_upload import read_file_with_limit, sanitize_filename, validate_upload_file
from app.services import dataset_service

router = APIRouter()

# Mounted separately (no {project_id} prefix) by app/api/v1/router.py.
top_router = APIRouter()


@router.post("/upload", summary="Upload a dataset to my project")
async def upload_dataset(project: OwnedProject, file: UploadFile = File(...)) -> dict:
    # Validate file
    validate_upload_file(file)
    
    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)
    
    # Read with size limit
    content = await read_file_with_limit(file, max_size=settings.MAX_UPLOAD_SIZE)
    
    return {
        "project_id": str(project.id),
        "filename": safe_filename,
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "status": "uploaded",
    }


@router.get("", summary="List datasets in my project")
@router.get("/", include_in_schema=False)
async def list_datasets(project: OwnedProject) -> list:
    return []


@top_router.get(
    "/resolve",
    summary="Check whether a dataset filename is available for a run",
)
async def resolve_dataset(
    user: CurrentUser,
    session: DbSession,
    name: str = Query(..., min_length=1, description="Dataset filename, e.g. churn.csv"),
    workspace_id: Optional[UUID] = Query(None, description="Restrict to one workspace"),
) -> dict:
    """Preflight probe used before a pipeline run is queued.

    Returns 200 with ``available: false`` rather than 404 — "not found" is an
    expected answer here, not an error, and the frontend keys the upload
    prompt off the flag.
    """
    return await dataset_service.resolve_for_user(session, user.id, name, workspace_id)


@top_router.post(
    "/upload",
    summary="Upload a dataset file so it becomes resolvable by the pipeline",
)
async def upload_dataset_file(
    user: CurrentUser,
    file: UploadFile = File(...),
    workspace_id: Optional[UUID] = Query(None),
) -> dict:
    """Persist an uploaded file into the upload directory.

    The worker resolves datasets from ``settings.UPLOAD_DIR`` before it ever
    touches object storage, so storing the bytes here is what makes the
    dataset resolvable by filename on the next run.
    """
    validate_upload_file(file)
    content = await read_file_with_limit(file, max_size=settings.MAX_UPLOAD_SIZE)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    stored = dataset_service.store_upload(file.filename or "", content)
    return {
        **stored,
        "original_filename": file.filename,
        "content_type": file.content_type,
        "status": "uploaded",
    }
