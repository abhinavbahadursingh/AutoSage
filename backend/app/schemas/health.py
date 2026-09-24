"""Pydantic schemas for health responses."""
from typing import Dict

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="'healthy' or 'degraded'")
    service: str = Field(default="autosage-backend")
    version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    checks: Dict[str, str] = Field(default_factory=dict)
