from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

class RunCreate(BaseModel):
    user_prompt: str
    dataset_id: UUID

class RunResponse(BaseModel):
    id: UUID
    status: str
    user_prompt: str
    final_metrics: Dict[str, Any]
    artifact_uri: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
