"""Drop unique constraint on scheduled_reconciliations.date to allow multiple schedules per day.

Revision ID: 008_drop_schedule_date_unique
Revises: 007_ds_date_range_backfill
"""
from typing import Sequence, Union
from alembic import op

revision: str = "008_drop_schedule_date_unique"
down_revision: Union[str, None] = "007_ds_date_range_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("scheduled_reconciliations_date_key", "scheduled_reconciliations", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("scheduled_reconciliations_date_key", "scheduled_reconciliations", ["date"])
