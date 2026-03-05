"""Add missing LMS schedule columns for existing deployments.

Revision ID: 004_add_lms_schedule_columns
Revises: 003_email_ingestion
Create Date: 2026-03-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004_add_lms_schedule_columns"
down_revision: Union[str, None] = "003_email_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill columns that may be missing if the 003 migration was applied
    # before LMS schedule fields were introduced.
    op.execute(
        """
        ALTER TABLE scheduled_reconciliations
        ADD COLUMN IF NOT EXISTS lms_source_id UUID,
        ADD COLUMN IF NOT EXISTS lms_ingested_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE scheduled_reconciliations
        DROP COLUMN IF EXISTS lms_ingested_at,
        DROP COLUMN IF EXISTS lms_source_id
        """
    )
