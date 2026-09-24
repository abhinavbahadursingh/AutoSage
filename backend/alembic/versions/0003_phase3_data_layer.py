"""0003: Phase 3/4 data layer — workspaces, experiments, and lineage tables.

New tables (all UUID PKs, created/updated timestamps, JSONB metadata):
- ``workspaces`` (owner -> users, cascade)
- ``experiments`` (workspace FK, status, config/result JSONB, retry counters)
- ``pipelines``, ``agent_executions``, ``decisions``, ``verifications``,
  ``ml_runs``, ``artifacts`` (experiment-scoped lineage, cascade deletes)

Existing tables (additive only — no data rewrite, NULL-safe):
- ``datasets``: + ``workspace_id`` (nullable FK, SET NULL), + ``updated_at``
- ``pipeline_runs``: + ``experiment_id`` (nullable FK, SET NULL), + ``updated_at``
- ``evidence_trail_nodes`` / ``verified_memories``: + ``updated_at``
- B-tree indexes on all new and previously unindexed foreign keys.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase3_data_layer"
down_revision: Union[str, Sequence[str], None] = "0002_users_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    # -- workspaces ------------------------------------------------------
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])

    # -- experiments -----------------------------------------------------
    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="CREATED"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("result_summary", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_experiments_workspace_id", "experiments", ["workspace_id"])
    op.create_index("ix_experiments_status", "experiments", ["status"])
    op.create_index(
        "ix_experiments_workspace_status", "experiments", ["workspace_id", "status"]
    )

    # -- pipelines -------------------------------------------------------
    op.create_table(
        "pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("definition", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_pipelines_experiment_id", "pipelines", ["experiment_id"])
    op.create_index("ix_pipelines_status", "pipelines", ["status"])

    # -- agent_executions ------------------------------------------------
    op.create_table(
        "agent_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("output_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_agent_executions_experiment_id", "agent_executions", ["experiment_id"]
    )
    op.create_index(
        "ix_agent_executions_pipeline_id", "agent_executions", ["pipeline_id"]
    )
    op.create_index("ix_agent_executions_agent_name", "agent_executions", ["agent_name"])
    op.create_index("ix_agent_executions_status", "agent_executions", ["status"])
    op.create_index(
        "ix_agent_executions_experiment_agent",
        "agent_executions",
        ["experiment_id", "agent_name"],
    )

    # -- decisions -------------------------------------------------------
    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_type", sa.String(100), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_decisions_experiment_id", "decisions", ["experiment_id"])
    op.create_index(
        "ix_decisions_agent_execution_id", "decisions", ["agent_execution_id"]
    )
    op.create_index("ix_decisions_decision_type", "decisions", ["decision_type"])

    # -- ml_runs ---------------------------------------------------------
    op.create_table(
        "ml_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("mlflow_run_id", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_ml_runs_experiment_id", "ml_runs", ["experiment_id"])
    op.create_index("ix_ml_runs_status", "ml_runs", ["status"])
    op.create_index("ix_ml_runs_mlflow_run_id", "ml_runs", ["mlflow_run_id"])

    # -- verifications ---------------------------------------------------
    op.create_table(
        "verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ml_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ml_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("check_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_verifications_experiment_id", "verifications", ["experiment_id"])
    op.create_index("ix_verifications_ml_run_id", "verifications", ["ml_run_id"])
    op.create_index("ix_verifications_check_name", "verifications", ["check_name"])
    op.create_index("ix_verifications_status", "verifications", ["status"])
    op.create_index(
        "ix_verifications_experiment_check",
        "verifications",
        ["experiment_id", "check_name"],
    )

    # -- artifacts -------------------------------------------------------
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "ml_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ml_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False, server_default="file"),
        sa.Column("uri", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_artifacts_experiment_id", "artifacts", ["experiment_id"])
    op.create_index("ix_artifacts_ml_run_id", "artifacts", ["ml_run_id"])
    op.create_index("ix_artifacts_pipeline_id", "artifacts", ["pipeline_id"])
    op.create_index("ix_artifacts_kind", "artifacts", ["kind"])

    # -- enrich existing tables (additive, NULL-safe) ---------------------
    op.add_column(
        "datasets",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_datasets_workspace_id_workspaces",
        "datasets",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_datasets_workspace_id", "datasets", ["workspace_id"])
    op.add_column("datasets", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    op.add_column(
        "pipeline_runs",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_pipeline_runs_experiment_id_experiments",
        "pipeline_runs",
        "experiments",
        ["experiment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_pipeline_runs_experiment_id", "pipeline_runs", ["experiment_id"])
    op.create_index("ix_pipeline_runs_project_id", "pipeline_runs", ["project_id"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])
    op.add_column("pipeline_runs", sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.create_index(
        "ix_evidence_trail_nodes_run_id", "evidence_trail_nodes", ["run_id"]
    )
    op.add_column(
        "evidence_trail_nodes", sa.Column("updated_at", sa.DateTime(), nullable=True)
    )

    op.create_index(
        "ix_verified_memories_source_run_id", "verified_memories", ["source_run_id"]
    )
    op.create_index("ix_verified_memories_task_type", "verified_memories", ["task_type"])
    op.add_column(
        "verified_memories", sa.Column("updated_at", sa.DateTime(), nullable=True)
    )

    op.create_index("ix_projects_user_id", "projects", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_user_id", table_name="projects")

    op.drop_column("verified_memories", "updated_at")
    op.drop_index("ix_verified_memories_task_type", table_name="verified_memories")
    op.drop_index("ix_verified_memories_source_run_id", table_name="verified_memories")

    op.drop_column("evidence_trail_nodes", "updated_at")
    op.drop_index("ix_evidence_trail_nodes_run_id", table_name="evidence_trail_nodes")

    op.drop_column("pipeline_runs", "updated_at")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_project_id", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_experiment_id", table_name="pipeline_runs")
    op.drop_constraint(
        "fk_pipeline_runs_experiment_id_experiments", "pipeline_runs", type_="foreignkey"
    )
    op.drop_column("pipeline_runs", "experiment_id")

    op.drop_index("ix_datasets_project_id", table_name="datasets")
    op.drop_column("datasets", "updated_at")
    op.drop_index("ix_datasets_workspace_id", table_name="datasets")
    op.drop_constraint(
        "fk_datasets_workspace_id_workspaces", "datasets", type_="foreignkey"
    )
    op.drop_column("datasets", "workspace_id")

    op.drop_table("artifacts")
    op.drop_table("verifications")
    op.drop_table("ml_runs")
    op.drop_table("decisions")
    op.drop_table("agent_executions")
    op.drop_table("pipelines")
    op.drop_table("experiments")
    op.drop_table("workspaces")
