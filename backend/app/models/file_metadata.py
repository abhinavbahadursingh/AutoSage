"""File metadata SQLAlchemy Model (Phase 14).

Persists file catalog records with metadata for datasets, PDFs, and artifacts.
Integrates with Supabase Storage for actual blob storage.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class FileMetadata(Base):
    """File metadata catalog record.
    
    Tracks files stored in Supabase Storage with full metadata:
    - Identity: UUID, owner, workspace, experiment/run associations
    - File info: name, MIME type, size, category, SHA-256 hash
    - Storage: Supabase bucket, path, signed URL expiration
    - Timestamps: created, updated
    """
    __tablename__ = "file_metadata"
    __table_args__ = (
        Index("ix_file_metadata_owner", "owner_id"),
        Index("ix_file_metadata_workspace", "workspace_id"),
        Index("ix_file_metadata_dataset", "dataset_id"),
        Index("ix_file_metadata_experiment", "experiment_id"),
        Index("ix_file_metadata_ml_run", "ml_run_id"),
        Index("ix_file_metadata_category", "category"),
        Index("ix_file_metadata_sha256", "sha256_hash"),
        Index("ix_file_metadata_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Ownership
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Optional scoping
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ml_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ml_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # File identification
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    category = Column(String(20), nullable=False, index=True)  # dataset, pdf, artifact
    
    # Integrity
    sha256_hash = Column(String(64), nullable=False, index=True)
    
    # Storage location
    storage_bucket = Column(String(100), nullable=False)
    storage_path = Column(Text, nullable=False)
    
    # Additional metadata
    extra_metadata = Column("meta", JSONB, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    owner = relationship("User", back_populates="files", lazy="selectin")
    workspace = relationship("Workspace", back_populates="files", lazy="selectin")
    dataset = relationship("Dataset", back_populates="files", lazy="selectin")
    experiment = relationship("Experiment", back_populates="files", lazy="selectin")
    ml_run = relationship("MLRun", back_populates="files", lazy="selectin")

    def __repr__(self) -> str:
        return f"<FileMetadata id={self.id} name={self.original_filename!r} category={self.category!r}>"

    @property
    def is_dataset(self) -> bool:
        return self.category == "dataset"

    @property
    def is_pdf(self) -> bool:
        return self.category == "pdf"

    @property
    def is_artifact(self) -> bool:
        return self.category == "artifact"