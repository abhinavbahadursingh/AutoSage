"""0005: Experience Memory System — pgvector-backed experience storage.

New table:
- ``experience_memories``: stores verified claims, experiment outcomes, dataset
  insights, model selection experiences, preprocessing experiences, and agent
  decisions with vector embeddings for semantic similarity search.

Indexes:
- B-tree on workspace_id, experiment_id, source_run_id, memory_type, status,
  task_type for metadata filtering.
- HNSW index on embedding for fast ANN search (created after data load).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = '962a8aa593b7'
down_revision: Union[str, Sequence[str], None] = '0004_experiment_task_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experience_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("dataset_fingerprint", postgresql.JSONB(), nullable=False),
        sa.Column("solution_strategy", sa.Text(), nullable=False),
        sa.Column("achieved_metric_value", sa.Float(), nullable=True),
        sa.Column("metric_name", sa.String(100), nullable=True),
        sa.Column("memory_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )

    # Metadata filtering indexes
    op.create_index("ix_experience_memories_workspace_id", "experience_memories", ["workspace_id"])
    op.create_index("ix_experience_memories_experiment_id", "experience_memories", ["experiment_id"])
    op.create_index("ix_experience_memories_source_run_id", "experience_memories", ["source_run_id"])
    op.create_index("ix_experience_memories_memory_type", "experience_memories", ["memory_type"])
    op.create_index("ix_experience_memories_status", "experience_memories", ["status"])
    op.create_index("ix_experience_memories_task_type", "experience_memories", ["task_type"])
    op.create_index("ix_experience_memories_created_at", "experience_memories", ["created_at"])
    # Composite indexes for common filter combinations
    op.create_index(
        "ix_experience_memories_workspace_type_status",
        "experience_memories",
        ["workspace_id", "memory_type", "status"],
    )
    op.create_index(
        "ix_experience_memories_workspace_task_status",
        "experience_memories",
        ["workspace_id", "task_type", "status"],
    )

    # HNSW index for ANN search (requires data; create after data load if needed)
    # op.execute("CREATE INDEX ix_experience_memories_embedding_hnsw ON experience_memories USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_index("ix_experience_memories_workspace_task_status", table_name="experience_memories")
    op.drop_index("ix_experience_memories_workspace_type_status", table_name="experience_memories")
    op.drop_index("ix_experience_memories_created_at", table_name="experience_memories")
    op.drop_index("ix_experience_memories_task_type", table_name="experience_memories")
    op.drop_index("ix_experience_memories_status", table_name="experience_memories")
    op.drop_index("ix_experience_memories_memory_type", table_name="experience_memories")
    op.drop_index("ix_experience_memories_source_run_id", table_name="experience_memories")
    op.drop_index("ix_experience_memories_experiment_id", table_name="experience_memories")
    op.drop_index("ix_experience_memories_workspace_id", table_name="experience_memories")
    op.drop_table("experience_memories")
