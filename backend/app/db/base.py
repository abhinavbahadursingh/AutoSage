"""Declarative base + model registration for Alembic autogenerate.

Import every ORM model here so ``Base.metadata`` contains the full schema
when Alembic renders migrations.
"""
from app.models.base import Base  # noqa: F401
from app.models import (  # noqa: F401
    agent_execution,
    artifact,
    dataset,
    decision,
    evidence,
    experiment,
    file_metadata,
    memory,
    ml_run,
    pipeline,
    project,
    reproducibility,
    run,
    user,
    verification,
    workspace,
)

__all__ = ["Base"]
