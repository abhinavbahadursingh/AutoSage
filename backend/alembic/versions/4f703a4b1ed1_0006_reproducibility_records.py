"""0006: Reproducibility Records (Phase 17).

New table:
- ``reproducibility_records``: stores a complete reproducibility snapshot for
  every completed ML experiment, including dataset hash, code version,
  dependencies, environment, and MLflow linkage.

Relationships:
- ``experiment_id`` -> experiments.id (CASCADE delete)
- ``ml_run_id`` -> ml_runs.id (SET NULL)
- ``dataset_id`` -> datasets.id (SET NULL)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '4f703a4b1ed1'
down_revision: Union[str, Sequence[str], None] = '962a8aa593b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reproducibility_records",
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
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Dataset fingerprint
        sa.Column("dataset_sha256", sa.String(64), nullable=False),
        sa.Column("dataset_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("dataset_rows", sa.Integer(), nullable=True),
        sa.Column("dataset_columns", sa.Integer(), nullable=True),
        sa.Column("dataset_schema", postgresql.JSONB(), nullable=True),
        # Code / version information
        sa.Column("code_version", sa.String(255), nullable=True),
        sa.Column("code_repository", sa.String(500), nullable=True),
        sa.Column("code_branch", sa.String(255), nullable=True),
        sa.Column("code_dirty", sa.String(10), nullable=True),
        # Dependency versions
        sa.Column("python_version", sa.String(50), nullable=False),
        sa.Column("platform", sa.String(100), nullable=True),
        sa.Column("pip_freeze", postgresql.JSONB(), nullable=True),
        sa.Column("conda_env", postgresql.JSONB(), nullable=True),
        # Model & experiment configuration
        sa.Column("model_family", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("model_params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("experiment_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        # MLflow linkage
        sa.Column("mlflow_run_id", sa.String(255), nullable=True),
        sa.Column("mlflow_experiment_id", sa.String(255), nullable=True),
        sa.Column("mlflow_experiment_name", sa.String(255), nullable=True),
        # Runtime environment
        sa.Column("runtime_type", sa.String(50), nullable=True),
        sa.Column("docker_image", sa.String(500), nullable=True),
        sa.Column("docker_image_id", sa.String(255), nullable=True),
        sa.Column("container_id", sa.String(255), nullable=True),
        sa.Column("hardware_info", postgresql.JSONB(), nullable=True),
        # Artifact references
        sa.Column("artifact_uris", postgresql.JSONB(), nullable=True),
        sa.Column("model_artifact_uri", sa.String(500), nullable=True),
        sa.Column("log_artifact_uri", sa.String(500), nullable=True),
        # Metrics snapshot
        sa.Column("final_metrics", postgresql.JSONB(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Indexes
    op.create_index("ix_reproducibility_experiment_id", "reproducibility_records", ["experiment_id"])
    op.create_index("ix_reproducibility_ml_run_id", "reproducibility_records", ["ml_run_id"])
    op.create_index("ix_reproducibility_dataset_id", "reproducibility_records", ["dataset_id"])
    op.create_index("ix_reproducibility_mlflow_run_id", "reproducibility_records", ["mlflow_run_id"])


def downgrade() -> None:
    op.drop_index("ix_reproducibility_mlflow_run_id", table_name="reproducibility_records")
    op.drop_index("ix_reproducibility_dataset_id", table_name="reproducibility_records")
    op.drop_index("ix_reproducibility_ml_run_id", table_name="reproducibility_records")
    op.drop_index("ix_reproducibility_experiment_id", table_name="reproducibility_records")
    op.drop_table("reproducibility_records")
