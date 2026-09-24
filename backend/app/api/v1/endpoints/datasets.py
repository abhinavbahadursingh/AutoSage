"""Dataset endpoints (Phase 2: auth + workspace isolation + security hardening).

Real upload parsing, profiling, and persistence land in later phases; these
routes already enforce that only the owning user can touch a project's
datasets (401 without credentials, 404 for foreign projects).
"""
from fastapi import APIRouter, File, UploadFile

from app.api.deps import OwnedProject
from app.core.config import settings
from app.core.file_upload import read_file_with_limit, sanitize_filename, validate_upload_file

router = APIRouter()


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
