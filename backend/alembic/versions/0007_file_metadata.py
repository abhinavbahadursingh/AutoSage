"""0007: file metadata catalog (Phase 14).

New table:
- ``file_metadata``: catalog of files stored in Supabase Storage
  (datasets, PDFs, artifacts) with ownership/scoping FKs and SHA-256
  integrity hash. The ORM model shipped in Phase 14 without a matching
  migration, so every eager ``User.files`` selectin load failed with
  ``UndefinedTableError``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_file_metadata"
down_revision: Union[str, Sequence[str], None] = "4f703a4b1ed1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_metadata",
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
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("storage_bucket", sa.String(100), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Column-level index=True names (match the ORM model).
    op.create_index("ix_file_metadata_owner_id", "file_metadata", ["owner_id"])
    op.create_index("ix_file_metadata_workspace_id", "file_metadata", ["workspace_id"])
    op.create_index("ix_file_metadata_dataset_id", "file_metadata", ["dataset_id"])
    op.create_index("ix_file_metadata_experiment_id", "file_metadata", ["experiment_id"])
    op.create_index("ix_file_metadata_ml_run_id", "file_metadata", ["ml_run_id"])
    op.create_index("ix_file_metadata_category", "file_metadata", ["category"])
    op.create_index("ix_file_metadata_sha256_hash", "file_metadata", ["sha256_hash"])

    # Explicit __table_args__ Index names (match the ORM model).
    op.create_index("ix_file_metadata_owner", "file_metadata", ["owner_id"])
    op.create_index("ix_file_metadata_workspace", "file_metadata", ["workspace_id"])
    op.create_index("ix_file_metadata_dataset", "file_metadata", ["dataset_id"])
    op.create_index("ix_file_metadata_experiment", "file_metadata", ["experiment_id"])
    op.create_index("ix_file_metadata_ml_run", "file_metadata", ["ml_run_id"])
    op.create_index("ix_file_metadata_sha256", "file_metadata", ["sha256_hash"])
    op.create_index("ix_file_metadata_created", "file_metadata", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_file_metadata_created", table_name="file_metadata")
    op.drop_index("ix_file_metadata_sha256", table_name="file_metadata")
    op.drop_index("ix_file_metadata_ml_run", table_name="file_metadata")
    op.drop_index("ix_file_metadata_experiment", table_name="file_metadata")
    op.drop_index("ix_file_metadata_dataset", table_name="file_metadata")
    op.drop_index("ix_file_metadata_workspace", table_name="file_metadata")
    op.drop_index("ix_file_metadata_owner", table_name="file_metadata")
    op.drop_index("ix_file_metadata_sha256_hash", table_name="file_metadata")
    op.drop_index("ix_file_metadata_category", table_name="file_metadata")
    op.drop_index("ix_file_metadata_ml_run_id", table_name="file_metadata")
    op.drop_index("ix_file_metadata_experiment_id", table_name="file_metadata")
    op.drop_index("ix_file_metadata_dataset_id", table_name="file_metadata")
    op.drop_index("ix_file_metadata_workspace_id", table_name="file_metadata")
    op.drop_index("ix_file_metadata_owner_id", table_name="file_metadata")
    op.drop_table("file_metadata")
