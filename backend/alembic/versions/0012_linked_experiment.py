"""0012: link a verification session to a completed pipeline experiment.

Objective 4 checks are runtime audits: they need Decision, EvidenceTrailNode,
AgentExecution, and ExperienceMemory records. A fresh verification session
owns an empty experiment, so those checks report NOT_VERIFIED until a real
pipeline run populates its experiment. This migration adds an optional
``linked_experiment_id`` so a verification session can instead read facts
from a completed pipeline experiment the user already ran.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_linked_experiment"
down_revision = "0011_objective_verification_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "verification_sessions",
        sa.Column(
            "linked_experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("verification_sessions", "linked_experiment_id")
