"""0001: initial schema — pgvector extension + core tables.

Tables mirror the Phase 1 ORM models (projects, datasets, pipeline_runs,
evidence_trail_nodes, verified_memories). No seed data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("schema_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("profile_summary", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("final_metrics", postgresql.JSONB(), nullable=True),
        sa.Column("artifact_uri", sa.String(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "evidence_trail_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("evidence_trail_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("decision_type", sa.String(100), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("empirical_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "verified_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("dataset_fingerprint", postgresql.JSONB(), nullable=False),
        sa.Column("solution_strategy", sa.String(), nullable=False),
        sa.Column("achieved_metric_value", sa.Float(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("verified_memories")
    op.drop_table("evidence_trail_nodes")
    op.drop_table("pipeline_runs")
    op.drop_table("datasets")
    op.drop_table("projects")
