"""0011: persist the structured decision record of a verification session.

Code generation now also produces the decisions behind the code — algorithm,
hyperparameters, metrics, validation strategy, assumptions and alternatives,
each with a rationale/confidence/source only when one was genuinely produced.
They are stored beside the generated files so a reconnecting client renders
the same decision-evidence explorer, and so no consumer has to re-parse the
SSE frame history to read them.

Design-time records: storing them claims nothing about training or execution.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_objective_verification_decisions"
down_revision = "0010_objective_verification_codegen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "verification_sessions",
        sa.Column(
            "decision_records",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "verification_sessions",
        sa.Column(
            "design_record",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("verification_sessions", "design_record")
    op.drop_column("verification_sessions", "decision_records")
