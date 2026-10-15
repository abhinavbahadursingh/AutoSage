"""0009: fresh verification sessions.

Backs the Fresh Experiment Objective Verification flow. One row per
execution, owning the isolated experiment that execution created, so
objective checks can never read a previous session's facts.

Adds table:
- verification_sessions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_verification_sessions"
down_revision = "0008_verification_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("dataset_name", sa.String(255), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("events", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("overall_status", sa.String(20), nullable=True),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_verification_sessions_owner_created",
        "verification_sessions",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_verification_sessions_owner_id",
        "verification_sessions",
        ["owner_id"],
    )
    op.create_index(
        "ix_verification_sessions_workspace_id",
        "verification_sessions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_verification_sessions_experiment_id",
        "verification_sessions",
        ["experiment_id"],
    )
    op.create_index(
        "ix_verification_sessions_status",
        "verification_sessions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_verification_sessions_status", table_name="verification_sessions")
    op.drop_index(
        "ix_verification_sessions_experiment_id", table_name="verification_sessions"
    )
    op.drop_index(
        "ix_verification_sessions_workspace_id", table_name="verification_sessions"
    )
    op.drop_index("ix_verification_sessions_owner_id", table_name="verification_sessions")
    op.drop_index(
        "ix_verification_sessions_owner_created", table_name="verification_sessions"
    )
    op.drop_table("verification_sessions")