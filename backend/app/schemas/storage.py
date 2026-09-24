"""Storage Pydantic schemas (Phase 14)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FileMetadataBase(BaseModel):
    """Base file metadata fields."""
    original_filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)
    file_size_bytes: int = Field(..., ge=0)
    category: str = Field(..., pattern="^(dataset|pdf|artifact)$")
    sha256_hash: str = Field(..., min_length=64, max_length=64)
    storage_path: str = Field(..., min_length=1)
    storage_bucket: str = Field(..., min_length=1)


class FileMetadataCreate(FileMetadataBase):
    """File metadata creation request."""
    workspace_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    experiment_id: Optional[UUID] = None
    ml_run_id: Optional[UUID] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class FileMetadataRead(FileMetadataBase):
    """File metadata response."""
    id: UUID
    owner_id: UUID
    workspace_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    experiment_id: Optional[UUID] = None
    ml_run_id: Optional[UUID] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    """File upload response."""
    file_id: UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    category: str
    sha256_hash: str
    storage_path: str
    download_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileListResponse(BaseModel):
    """Paginated file list response."""
    items: List[FileMetadataRead]
    total: int
    page: int
    page_size: int


class SignedUrlResponse(BaseModel):
    """Signed URL response."""
    signed_url: str
    expires_at: datetime


class StorageErrorResponse(BaseModel):
    """Storage error response."""
    detail: str
    code: str
    path: str


# Category-specific schemas
class DatasetFileUploadRequest(BaseModel):
    """Dataset file upload with dataset-specific metadata."""
    workspace_id: UUID
    dataset_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    # Dataset-specific
    delimiter: Optional[str] = ","
    has_header: bool = True
    encoding: Optional[str] = "utf-8"


class DatasetFileCreate(BaseModel):
    """Dataset file creation combining file metadata and dataset info."""
    file_metadata: FileMetadataCreate
    dataset_info: DatasetFileUploadRequest


# Internal models for service layer
class FileRecord(BaseModel):
    """Internal file record for service operations."""
    id: UUID
    owner_id: UUID
    workspace_id: Optional[UUID]
    dataset_id: Optional[UUID]
    experiment_id: Optional[UUID]
    ml_run_id: Optional[UUID]
    original_filename: str
    content_type: str
    file_size_bytes: int
    category: str
    sha256_hash: str
    storage_path: str
    storage_bucket: str
    extra_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UploadResult(BaseModel):
    """Result of file upload operation."""
    file_record: FileRecord
    signed_url: Optional[str] = None