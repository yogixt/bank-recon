"""Add internal data-date range columns to data_sources.

Revision ID: 006_add_data_source_date_range
Revises: 005_backfill_lms_tables
Create Date: 2026-03-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006_add_data_source_date_range"
down_revision: Union[str, None] = "005_backfill_lms_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE data_sources
        ADD COLUMN IF NOT EXISTS data_date_from DATE,
        ADD COLUMN IF NOT EXISTS data_date_to DATE
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE data_sources
        DROP COLUMN IF EXISTS data_date_to,
        DROP COLUMN IF EXISTS data_date_from
        """
    )
