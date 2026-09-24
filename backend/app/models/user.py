"""User SQLAlchemy Model (Phase 2 authentication).

Better Auth (Next.js frontend) is the identity provider and owns the
signup/login/session lifecycle. The backend verifies Better Auth JWTs
statelessly and lazily provisions a matching row here on first sight so that
workspace isolation (``projects.user_id -> users.id``) works without a
separate sync step.

Better Auth table mapping (frontend config)::

    user: { modelName: "users" }
    advanced: { database: { generateId: "uuid" } }

so that Better Auth's ``user.id`` (JWT ``sub``) matches ``users.id``.
Session/account/verification tables live on the Better Auth side only;
the API never reads them.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    image = Column(String, nullable=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    projects = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )
    workspaces = relationship(
        "Workspace", back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )
    files = relationship(
        "FileMetadata", back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User id={self.id} email={self.email!r}>"
