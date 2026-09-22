from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Dict, Any

class DatasetResponse(BaseModel):
    id: UUID
    original_filename: str
    file_size_bytes: int
    schema_metadata: Dict[str, Any]
    profile_summary: Dict[str, Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
