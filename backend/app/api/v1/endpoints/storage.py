"""File storage endpoints (Phase 14).

Upload, download, list, and manage files (datasets, PDFs, artifacts)
with Supabase Storage backend and PostgreSQL metadata persistence.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import BadRequestError, NotFoundError
from app.engine.storage.service import (
    get_storage_service_instance,
    FILE_CATEGORY_DATASET,
    FILE_CATEGORY_PDF,
    FILE_CATEGORY_ARTIFACT,
)
from app.schemas.storage import (
    FileMetadataRead,
    FileUploadResponse,
    FileListResponse,
    SignedUrlResponse,
    FileMetadataCreate,
)
from app.db.session import get_db

router = APIRouter(tags=["Storage"])


# Allowed categories for upload
ALLOWED_CATEGORIES = {FILE_CATEGORY_DATASET, FILE_CATEGORY_PDF, FILE_CATEGORY_ARTIFACT}


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
)
async def upload_file(
    user: CurrentUser,
    session: DbSession,
    file: UploadFile = File(...),
    category: Optional[str] = Form(None, description="File category: dataset, pdf, or artifact"),
    workspace_id: Optional[str] = Form(None, description="Optional workspace ID for scoping"),
    dataset_id: Optional[str] = Form(None, description="Optional dataset ID for association"),
    experiment_id: Optional[str] = Form(None, description="Optional experiment ID for association"),
    ml_run_id: Optional[str] = Form(None, description="Optional ML run ID for association"),
) -> FileUploadResponse:
    """Upload a file to Supabase Storage.
    
    The file is validated for MIME type and size limits based on category:
    - **dataset**: CSV, Parquet, Excel, JSON (max 500MB)
    - **pdf**: PDF documents (max 100MB)
    - **artifact**: Models, archives, code, JSON (max 200MB)
    
    Category is auto-detected from MIME type and filename if not specified.
    """
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file not allowed")
    
    # Parse optional UUIDs
    workspace_uuid = UUID(workspace_id) if workspace_id else None
    dataset_uuid = UUID(dataset_id) if dataset_id else None
    experiment_uuid = UUID(experiment_id) if experiment_id else None
    ml_run_uuid = UUID(ml_run_id) if ml_run_id else None
    
    # Validate category
    if category and category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
        )
    
    # Get storage service
    storage_service = get_storage_service_instance()
    
    # Upload file
    try:
        result = await storage_service.upload_file(
            session=session,
            owner_id=user.id,
            file_stream=file.file,
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            category=category,
            workspace_id=workspace_uuid,
            dataset_id=dataset_uuid,
            experiment_id=experiment_uuid,
            ml_run_id=ml_run_uuid,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    
    return FileUploadResponse(
        file_id=result.file_record.id,
        original_filename=result.file_record.original_filename,
        content_type=result.file_record.content_type,
        file_size_bytes=result.file_record.file_size_bytes,
        category=result.file_record.category,
        sha256_hash=result.file_record.sha256_hash,
        storage_path=result.file_record.storage_path,
        download_url=result.signed_url,
        created_at=result.file_record.created_at,
    )


@router.get(
    "/files",
    response_model=FileListResponse,
    summary="List my files",
)
async def list_files(
    user: CurrentUser,
    session: DbSession,
    workspace_id: Optional[UUID] = Query(None, description="Filter by workspace"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> FileListResponse:
    """List files owned by the current user with optional filters."""
    if category and category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
        )
    
    storage_service = get_storage_service_instance()
    
    return await storage_service.list_files(
        session=session,
        owner_id=user.id,
        workspace_id=workspace_id,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/files/{file_id}",
    response_model=FileMetadataRead,
    summary="Get file metadata",
)
async def get_file(
    user: CurrentUser,
    session: DbSession,
    file_id: UUID,
) -> FileMetadataRead:
    """Get file metadata by ID."""
    storage_service = get_storage_service_instance()
    
    try:
        file_record = await storage_service.get_file(session, file_id, user.id)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {e}")
    
    return FileMetadataRead.from_orm(file_record)


@router.get(
    "/files/{file_id}/download",
    summary="Download a file",
)
async def download_file(
    user: CurrentUser,
    session: DbSession,
    file_id: UUID,
):
    """Download file content from Supabase Storage.
    
    Returns the file as a streaming response with appropriate headers.
    """
    storage_service = get_storage_service_instance()
    
    try:
        file_data, file_record = await storage_service.download_file(session, file_id, user.id)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")
    
    from fastapi.responses import StreamingResponse
    import io
    
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type=file_record.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.original_filename}"',
            "Content-Length": str(file_record.file_size_bytes),
        },
    )


@router.post(
    "/files/{file_id}/signed-url",
    response_model=SignedUrlResponse,
    summary="Create signed download URL",
)
async def create_signed_url(
    user: CurrentUser,
    session: DbSession,
    file_id: UUID,
    expires_in: int = Form(3600, ge=60, le=86400, description="URL expiry in seconds (1 min - 24 hours)"),
) -> SignedUrlResponse:
    """Create a signed URL for temporary file access.
    
    The URL expires after the specified number of seconds (default 1 hour).
    """
    storage_service = get_storage_service_instance()
    
    try:
        result = await storage_service.create_signed_url(
            session=session,
            file_id=file_id,
            owner_id=user.id,
            expires_in=expires_in,
        )
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"Signed URL creation failed: {e}")
    
    return result


@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file",
)
async def delete_file(
    user: CurrentUser,
    session: DbSession,
    file_id: UUID,
):
    """Delete a file from Supabase Storage and remove its metadata."""
    storage_service = get_storage_service_instance()
    
    try:
        await storage_service.delete_file(session, file_id, user.id)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


@router.get(
    "/stats",
    summary="Get storage statistics for current user",
)
async def get_storage_stats(
    user: CurrentUser,
    session: DbSession,
) -> dict:
    """Get storage usage statistics for the current user."""
    storage_service = get_storage_service_instance()
    
    stats = await storage_service.get_storage_stats(session, user.id)
    return stats