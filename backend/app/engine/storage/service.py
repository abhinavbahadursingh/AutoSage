"""Storage service layer (Phase 14).

Business logic for file upload, download, listing, and metadata management.
Uses SupabaseStorageClient for blob operations and SQLAlchemy for metadata persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError
from app.engine.storage.client import (
    SupabaseStorageClient,
    compute_sha256,
    validate_file,
    generate_storage_path,
    guess_category_from_mime,
    FILE_CATEGORY_DATASET,
    FILE_CATEGORY_PDF,
    FILE_CATEGORY_ARTIFACT,
    get_supabase_client,
)
from app.models.file_metadata import FileMetadata
from app.schemas.storage import (
    FileMetadataCreate,
    FileMetadataRead,
    FileUploadResponse,
    FileListResponse,
    SignedUrlResponse,
    FileRecord,
    UploadResult,
)


class StorageService:
    """High-level storage service for file operations."""
    
    def __init__(
        self,
        storage_client: Optional[SupabaseStorageClient] = None,
    ):
        self.client = storage_client or get_supabase_client()
    
    async def upload_file(
        self,
        session: AsyncSession,
        owner_id: UUID,
        file_stream: BinaryIO,
        filename: str,
        content_type: str,
        file_size: int,
        category: Optional[str] = None,
        workspace_id: Optional[UUID] = None,
        dataset_id: Optional[UUID] = None,
        experiment_id: Optional[UUID] = None,
        ml_run_id: Optional[UUID] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> "UploadResult":
        """Upload a file to Supabase Storage and persist metadata."""
        # Validate file
        try:
            validated_category = validate_file(filename, content_type, file_size, category)
        except Exception as e:
            raise BadRequestError(f"File validation failed: {e}")
        
        # Compute SHA-256 hash
        file_stream.seek(0)
        sha256_hash = compute_sha256(file_stream)
        
        # Check for duplicate hash
        existing = await self._find_by_hash(session, owner_id, sha256_hash)
        if existing:
            raise BadRequestError(
                f"File with same content already exists: {existing.original_filename}",
                code="DUPLICATE_FILE"
            )
        
        # Generate storage path
        storage_path = generate_storage_path(
            category=validated_category,
            owner_id=owner_id,
            workspace_id=workspace_id,
            filename=filename,
        )
        
        # Upload to Supabase Storage
        file_stream.seek(0)
        file_data = file_stream.read()
        
        try:
            self.client.upload(
                path=storage_path,
                file_data=file_data,
                content_type=content_type,
                upsert=False,
            )
        except Exception as e:
            raise ServiceUnavailableError(f"Storage upload failed: {e}")
        
        # Create metadata record
        file_record = FileMetadata(
            owner_id=owner_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            experiment_id=experiment_id,
            ml_run_id=ml_run_id,
            original_filename=filename,
            content_type=content_type,
            file_size_bytes=len(file_data),
            category=validated_category,
            sha256_hash=sha256_hash,
            storage_bucket=self.client.bucket_name,
            storage_path=storage_path,
            extra_metadata=extra_metadata or {},
        )
        
        session.add(file_record)
        await session.flush()
        await session.refresh(file_record)
        
        # Generate signed download URL (valid for 1 hour)
        signed_url = self.client.create_signed_url(storage_path, expires_in=3600)
        
        return UploadResult(
            file_record=FileRecord.from_orm(file_record),
            signed_url=signed_url,
        )
    
    async def _find_by_hash(
        self, session: AsyncSession, owner_id: UUID, sha256_hash: str
    ) -> Optional[FileMetadata]:
        """Find existing file by SHA-256 hash for the same owner."""
        stmt = select(FileMetadata).where(
            FileMetadata.owner_id == owner_id,
            FileMetadata.sha256_hash == sha256_hash,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_file(
        self,
        session: AsyncSession,
        file_id: UUID,
        owner_id: UUID,
    ) -> "FileRecord":
        """Get file metadata by ID (owner-scoped)."""
        stmt = select(FileMetadata).where(
            FileMetadata.id == file_id,
            FileMetadata.owner_id == owner_id,
        )
        result = await session.execute(stmt)
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise NotFoundError(f"File {file_id} not found")
        
        return FileRecord.from_orm(file_record)
    
    async def download_file(
        self,
        session: AsyncSession,
        file_id: UUID,
        owner_id: UUID,
    ) -> tuple[bytes, "FileRecord"]:
        """Download file content from Supabase Storage."""
        file_record = await self.get_file(session, file_id, owner_id)
        
        try:
            file_data = self.client.download(file_record.storage_path)
        except Exception as e:
            raise ServiceUnavailableError(f"Storage download failed: {e}")
        
        return file_data, file_record
    
    async def delete_file(
        self,
        session: AsyncSession,
        file_id: UUID,
        owner_id: UUID,
    ) -> None:
        """Delete file from storage and metadata from database."""
        file_record = await self.get_file(session, file_id, owner_id)
        
        # Delete from Supabase Storage
        try:
            self.client.delete(file_record.storage_path)
        except Exception as e:
            import logging
            logging.warning(f"Storage delete failed for {file_record.storage_path}: {e}")
        
        # Delete metadata
        await session.delete(file_record)
        await session.flush()
    
    async def list_files(
        self,
        session: AsyncSession,
        owner_id: UUID,
        workspace_id: Optional[UUID] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> "FileListResponse":
        """List files with optional filters (owner-scoped)."""
        stmt = select(FileMetadata).where(FileMetadata.owner_id == owner_id)
        
        if workspace_id:
            stmt = stmt.where(FileMetadata.workspace_id == workspace_id)
        if category:
            stmt = stmt.where(FileMetadata.category == category)
        
        # Order by newest first
        stmt = stmt.order_by(FileMetadata.created_at.desc())
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar()
        
        # Apply pagination
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        
        result = await session.execute(stmt)
        items = result.scalars().all()
        
        return FileListResponse(
            items=[FileMetadataRead.from_orm(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def create_signed_url(
        self,
        session: AsyncSession,
        file_id: UUID,
        owner_id: UUID,
        expires_in: int = 3600,
    ) -> "SignedUrlResponse":
        """Create a signed URL for temporary file access."""
        file_record = await self.get_file(session, file_id, owner_id)
        
        url = self.client.create_signed_url(file_record.storage_path, expires_in)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        return SignedUrlResponse(signed_url=url, expires_at=expires_at)
    
    async def get_storage_stats(
        self,
        session: AsyncSession,
        owner_id: UUID,
    ) -> Dict[str, Any]:
        """Get storage statistics for a user."""
        # Total files and size
        stmt = select(
            func.count(FileMetadata.id),
            func.sum(FileMetadata.file_size_bytes),
        ).where(FileMetadata.owner_id == owner_id)
        
        result = await session.execute(stmt)
        total_files, total_bytes = result.one()
        
        # By category
        cat_stmt = select(
            FileMetadata.category,
            func.count(FileMetadata.id),
            func.sum(FileMetadata.file_size_bytes),
        ).where(FileMetadata.owner_id == owner_id).group_by(FileMetadata.category)
        
        cat_result = await session.execute(cat_stmt)
        by_category = {
            row.category: {"count": row[1], "size_bytes": row[2] or 0}
            for row in cat_result.all()
        }
        
        return {
            "total_files": total_files or 0,
            "total_bytes": total_bytes or 0,
            "by_category": by_category,
        }


# Global service instance
_storage_service_instance: Optional["StorageService"] = None


def get_storage_service_instance() -> "StorageService":
    """Get or create the global storage service instance."""
    global _storage_service_instance
    if _storage_service_instance is None:
        _storage_service_instance = StorageService()
    return _storage_service_instance


def set_storage_service_instance(service: Optional["StorageService"]) -> None:
    """Replace global storage service instance (for testing)."""
    global _storage_service_instance
    _storage_service_instance = service