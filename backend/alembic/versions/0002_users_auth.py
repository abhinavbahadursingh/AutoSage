"""0002: users table + project ownership (Phase 2 authentication).

- Creates ``users`` (Better Auth identity mirror; frontend maps
  ``user.modelName`` to ``users`` with UUID ids).
- Adds ``projects.user_id -> users.id`` FK with cascade delete.
- Existing Phase 1 databases have projects rows without users; the FK is
  added as nullable-then-not-null is unsafe offline, so: existing rows are
  backfilled is NOT possible without user ids — instead the constraint is
  added WITHOUT validating legacy rows? Simplest correct path for a
  pre-production Phase 1 schema: add the FK column constraint directly as
  NOT NULL (fresh environments). Deployments with legacy data should backfill
  ``user_id`` before upgrading.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_users_auth"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Phase 1 created projects.user_id with no FK; now constrain it.
    op.create_foreign_key(
        "fk_projects_user_id_users",
        "projects",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column("projects", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_constraint("fk_projects_user_id_users", "projects", type_="foreignkey")
    op.drop_column("projects", "updated_at")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
