"""Workspace SQLAlchemy Model (Phase 3 data layer).

A workspace is the top-level isolation boundary: it is owned by exactly one
user and contains experiments (plus their pipelines, runs, decisions,
evidence, verifications, memories, and artifacts). All experiment access is
scoped through workspace ownership — a user can never see another user's
workspace or anything inside it.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    meta = Column("meta", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    owner = relationship("User", back_populates="workspaces", lazy="selectin")
    experiments = relationship(
        "Experiment",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    datasets = relationship(
        "Dataset",
        back_populates="workspace",
        lazy="selectin",
    )
    files = relationship(
        "FileMetadata", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Workspace id={self.id} name={self.name!r}>"
