"""Dataset SQLAlchemy Model."""
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.models.base import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Optional workspace scoping for the Phase 3+ experiment world; datasets
    # uploaded under Phase 2 projects keep this NULL.
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    schema_metadata = Column(JSONB, default={})
    profile_summary = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="datasets", lazy="selectin")
    files = relationship(
        "FileMetadata", back_populates="dataset", cascade="all, delete-orphan", lazy="selectin"
    )
    reproducibility_records = relationship(
        "ReproducibilityRecord", back_populates="dataset", cascade="all, delete-orphan", lazy="selectin"
    )
