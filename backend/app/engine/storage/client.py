"""Supabase Storage client (Phase 14).

Low-level Supabase Storage operations: upload, download, delete, signed URLs.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional
from urllib.parse import urljoin

from supabase import create_client, Client

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError


# File type categories
FILE_CATEGORY_DATASET = "dataset"
FILE_CATEGORY_PDF = "pdf"
FILE_CATEGORY_ARTIFACT = "artifact"

ALLOWED_MIME_TYPES = {
    FILE_CATEGORY_DATASET: {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/parquet",
        "application/x-parquet",
        "application/octet-stream",
        "application/json",
        "text/plain",
    },
    FILE_CATEGORY_PDF: {
        "application/pdf",
    },
    FILE_CATEGORY_ARTIFACT: {
        "application/octet-stream",
        "application/json",
        "application/x-python-code",
        "text/plain",
        "application/zip",
        "application/x-tar",
        "application/gzip",
        "application/x-gzip",
    },
}

MAX_FILE_SIZES = {
    FILE_CATEGORY_DATASET: 500 * 1024 * 1024,
    FILE_CATEGORY_PDF: 100 * 1024 * 1024,
    FILE_CATEGORY_ARTIFACT: 200 * 1024 * 1024,
}

DEFAULT_CATEGORY = FILE_CATEGORY_ARTIFACT


class StorageError(Exception):
    """Base exception for storage operations."""
    def __init__(self, message: str, error_type: str = "StorageError"):
        super().__init__(message)
        self.error_type = error_type


class FileValidationError(StorageError):
    """File validation failed."""
    def __init__(self, message: str):
        super().__init__(message, "FileValidationError")


class SupabaseStorageError(StorageError):
    """Supabase Storage operation failed."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "SupabaseStorageError")
        self.original_error = original_error


def compute_sha256(stream: BinaryIO) -> str:
    """Compute SHA-256 hash of a file stream."""
    hasher = hashlib.sha256()
    for chunk in iter(lambda: stream.read(8192), b""):
        hasher.update(chunk)
    stream.seek(0)
    return hasher.hexdigest()


def guess_category_from_mime(mime_type: str) -> str:
    """Guess file category from MIME type."""
    for category, types in ALLOWED_MIME_TYPES.items():
        if mime_type in types:
            return category
    return DEFAULT_CATEGORY


def guess_category_from_filename(filename: str) -> str:
    """Guess file category from filename extension."""
    ext = Path(filename).suffix.lower()
    if ext in {".csv", ".parquet", ".xlsx", ".xls", ".json", ".tsv"}:
        return FILE_CATEGORY_DATASET
    if ext == ".pdf":
        return FILE_CATEGORY_PDF
    if ext in {".pkl", ".joblib", ".pt", ".pth", ".model", ".zip", ".tar", ".gz", ".json", ".txt"}:
        return FILE_CATEGORY_ARTIFACT
    return DEFAULT_CATEGORY


def validate_file(
    filename: str,
    content_type: str,
    file_size: int,
    category: Optional[str] = None,
) -> str:
    """Validate file against allowed types and size limits."""
    if category is None:
        category = guess_category_from_mime(content_type)
        if category == DEFAULT_CATEGORY:
            category = guess_category_from_filename(filename)
    
    allowed_types = ALLOWED_MIME_TYPES.get(category, set())
    if content_type not in allowed_types:
        if content_type == "application/octet-stream":
            guessed = guess_category_from_filename(filename)
            if guessed != category:
                raise FileValidationError(
                    f"File extension doesn't match expected category '{category}'"
                )
        else:
            raise FileValidationError(
                f"MIME type '{content_type}' not allowed for category '{category}'. "
                f"Allowed: {', '.join(sorted(allowed_types))}"
            )
    
    max_size = MAX_FILE_SIZES.get(category, MAX_FILE_SIZES[DEFAULT_CATEGORY])
    if file_size > max_size:
        raise FileValidationError(
            f"File size {file_size} bytes exceeds limit of {max_size} bytes for category '{category}'"
        )
    
    return category


def generate_storage_path(
    category: str,
    owner_id: uuid.UUID,
    workspace_id: Optional[uuid.UUID] = None,
    filename: Optional[str] = None,
) -> str:
    """Generate a unique storage path for a file."""
    workspace_part = str(workspace_id) if workspace_id else "global"
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    
    if filename:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        name_part = f"{unique_id}_{safe_name}"
    else:
        name_part = unique_id
    
    return f"{category}/{owner_id}/{workspace_part}/{timestamp}/{name_part}"


class SupabaseStorageClient:
    """Low-level Supabase Storage client for blob operations."""
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        bucket_name: str = "autosage-files",
    ):
        self.bucket_name = bucket_name
        self.supabase_url = supabase_url or settings.SUPABASE_URL
        self.supabase_key = supabase_key or settings.SUPABASE_SERVICE_ROLE_KEY
        self._client: Optional[Client] = None
        
        if not self.supabase_url or not self.supabase_key:
            raise ServiceUnavailableError(
                "Supabase credentials not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
    
    @property
    def client(self) -> Client:
        """Lazy Supabase client initialization."""
        if self._client is None:
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client
    
    def _ensure_bucket(self) -> None:
        """Ensure the storage bucket exists."""
        try:
            buckets = self.client.storage.list_buckets()
            if not any(b.name == self.bucket_name for b in buckets):
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={"public": False, "file_size_limit": 524288000},
                )
        except Exception as e:
            raise ServiceUnavailableError(f"Failed to ensure bucket: {e}", e)
    
    def upload(
        self,
        path: str,
        file_data: bytes,
        content_type: str,
        upsert: bool = False,
    ) -> dict:
        """Upload file to Supabase Storage."""
        self._ensure_bucket()
        try:
            response = self.client.storage.from_(self.bucket_name).upload(
                path=path,
                file=file_data,
                file_options={
                    "content-type": content_type,
                    "upsert": "true" if upsert else "false",
                },
            )
            return response
        except Exception as e:
            raise SupabaseStorageError(f"Upload failed: {e}", e)
    
    def download(self, path: str) -> bytes:
        """Download file from Supabase Storage."""
        try:
            return self.client.storage.from_(self.bucket_name).download(path)
        except Exception as e:
            raise SupabaseStorageError(f"Download failed: {e}", e)
    
    def delete(self, path: str) -> dict:
        """Delete file from Supabase Storage."""
        try:
            return self.client.storage.from_(self.bucket_name).remove([path])
        except Exception as e:
            raise SupabaseStorageError(f"Delete failed: {e}", e)
    
    def get_public_url(self, path: str) -> str:
        """Get public URL for a file."""
        return self.client.storage.from_(self.bucket_name).get_public_url(path)
    
    def create_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """Create a signed URL for temporary access."""
        try:
            response = self.client.storage.from_(self.bucket_name).create_signed_url(
                path, expires_in
            )
            return response.get("signedURL", "")
        except Exception as e:
            raise SupabaseStorageError(f"Signed URL creation failed: {e}", e)
    
    def list_files(self, folder: str = "") -> list:
        """List files in a folder."""
        try:
            return self.client.storage.from_(self.bucket_name).list(folder)
        except Exception as e:
            raise SupabaseStorageError(f"List failed: {e}", e)


# Global client instance
_supabase_client: Optional[SupabaseStorageClient] = None


def get_supabase_client() -> SupabaseStorageClient:
    """Get or create the global Supabase storage client."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseStorageClient()
    return _supabase_client


def set_supabase_client(client: Optional[SupabaseStorageClient]) -> None:
    """Replace global Supabase client (for testing)."""
    global _supabase_client
    _supabase_client = client


# Re-export utilities
__all__ = [
    "SupabaseStorageClient",
    "compute_sha256",
    "validate_file",
    "generate_storage_path",
    "guess_category_from_mime",
    "guess_category_from_filename",
    "FILE_CATEGORY_DATASET",
    "FILE_CATEGORY_PDF",
    "FILE_CATEGORY_ARTIFACT",
    "get_supabase_client",
    "StorageError",
    "FileValidationError",
    "SupabaseStorageError",
]