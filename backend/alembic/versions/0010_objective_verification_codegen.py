"""0010: store generated code and activity for objective verification.

Code generation is part of the verification demonstration flow but never
executes anything. The generated files + the activity log are persisted so a
reconnecting (or later-subscribing) client renders the same code, the same
edits-vs-original delta, and never sees fabricated output.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_objective_verification_codegen"
down_revision = "0009_verification_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "verification_sessions",
        sa.Column(
            "generated_files",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "verification_sessions",
        sa.Column(
            "activity_log",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "verification_sessions",
        sa.Column("code_generation_status", sa.String(40), nullable=True),
    )
    op.add_column(
        "verification_sessions",
        sa.Column("code_generation_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("verification_sessions", "code_generation_message")
    op.drop_column("verification_sessions", "code_generation_status")
    op.drop_column("verification_sessions", "activity_log")
    op.drop_column("verification_sessions", "generated_files")