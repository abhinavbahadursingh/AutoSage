"""0004: Phase 5 — Celery task id tracking on experiments.

Additive, NULL-safe: ``experiments.celery_task_id`` stores the background
task id assigned at enqueue time (used for revoke-on-cancel and task-state
inspection). Existing rows keep NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_experiment_task_id"
down_revision: Union[str, Sequence[str], None] = "0003_phase3_data_layer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiments", sa.Column("celery_task_id", sa.String(255), nullable=True)
    )
    op.create_index(
        "ix_experiments_celery_task_id", "experiments", ["celery_task_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_experiments_celery_task_id", table_name="experiments")
    op.drop_column("experiments", "celery_task_id")
