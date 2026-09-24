"""File upload validation utilities (Phase 20A)."""
import os
import re
from typing import List, Optional

from fastapi import UploadFile, HTTPException, status

from app.core.config import settings


# Dangerous filename patterns
DANGEROUS_FILENAME_PATTERNS = [
    r"\.\.",           # Path traversal
    r"^[. ]",          # Starts with dot or space
    r"[<>:\"|?*]",     # Windows forbidden chars
    r"[\x00-\x1f]",    # Control characters
]

# Compile patterns
COMPILED_DANGEROUS_PATTERNS = [re.compile(p) for p in DANGEROUS_FILENAME_PATTERNS]


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for storage
        
    Raises:
        HTTPException: If filename is invalid
    """
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )
    
    # Check for dangerous patterns
    for pattern in COMPILED_DANGEROUS_PATTERNS:
        if pattern.search(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename: contains forbidden characters",
            )
    
    # Remove any directory components
    filename = os.path.basename(filename)
    
    # Limit length
    max_len = 255
    if len(filename) > max_len:
        name, ext = os.path.splitext(filename)
        filename = name[:max_len - len(ext)] + ext
    
    return filename


def validate_upload_file(file: UploadFile) -> None:
    """Validate uploaded file meets security requirements.
    
    Args:
        file: FastAPI UploadFile object
        
    Raises:
        HTTPException: If file fails validation
    """
    # Check content type
    allowed_types = settings.ALLOWED_UPLOAD_TYPES
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: {file.content_type}. "
                f"Allowed types: {', '.join(allowed_types)}"
            ),
        )
    
    # Check filename
    sanitize_filename(file.filename)
    
    # Note: File size is checked during reading, not here
    # because UploadFile doesn't know size until read


async def read_file_with_limit(
    file: UploadFile, 
    max_size: Optional[int] = None,
    chunk_size: int = 8192
) -> bytes:
    """Read uploaded file with size limit enforcement.
    
    Args:
        file: FastAPI UploadFile object
        max_size: Maximum allowed size in bytes (defaults to settings.MAX_UPLOAD_SIZE)
        chunk_size: Read chunk size
        
    Returns:
        File content as bytes
        
    Raises:
        HTTPException: If file exceeds size limit
    """
    if max_size is None:
        max_size = settings.MAX_UPLOAD_SIZE
    
    content = bytearray()
    total_read = 0
    
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        
        total_read += len(chunk)
        if total_read > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed ({max_size} bytes)",
            )
        
        content.extend(chunk)
    
    # Reset file position for potential re-reading
    await file.seek(0)
    
    return bytes(content)


def get_safe_filepath(upload_dir: str, filename: str) -> str:
    """Get safe filepath within upload directory.
    
    Args:
        upload_dir: Base upload directory
        filename: Sanitized filename
        
    Returns:
        Safe absolute filepath
        
    Raises:
        HTTPException: If path would escape upload directory
    """
    # Ensure upload directory exists
    os.makedirs(upload_dir, exist_ok=True)
    
    # Get absolute paths
    upload_dir = os.path.abspath(upload_dir)
    filepath = os.path.abspath(os.path.join(upload_dir, filename))
    
    # Verify filepath is within upload directory
    if not filepath.startswith(upload_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )
    
    return filepath