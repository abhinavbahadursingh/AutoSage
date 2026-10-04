"""0008: add missing columns to verifications table.

The Verification model evolved but the migration was not updated.
Adds:
- decisions (JSONB, not null, default '{}')
- overall_status (String, not null, default 'UNVERIFIED')
- overall_confidence (Float, nullable)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_verification_columns"
down_revision = "0007_file_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The table exists but may lack these columns
    op.add_column(
        "verifications",
        sa.Column(
            "decisions",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "verifications",
        sa.Column(
            "overall_status",
            sa.String(30),
            nullable=False,
            server_default="UNVERIFIED",
        ),
    )
    op.add_column(
        "verifications",
        sa.Column(
            "overall_confidence",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("verifications", "overall_confidence")
    op.drop_column("verifications", "overall_status")
    op.drop_column("verifications", "decisions")