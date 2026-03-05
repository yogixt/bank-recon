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
    # The unique constraint may have different names depending on how it was created.
    # Try to drop it; if it doesn't exist, that's fine — the goal is already met.
    op.execute("""
        DO $$
        DECLARE
            cname text;
        BEGIN
            SELECT conname INTO cname
            FROM pg_constraint
            WHERE conrelid = 'scheduled_reconciliations'::regclass
              AND contype = 'u'
              AND EXISTS (
                  SELECT 1 FROM unnest(conkey) k
                  JOIN pg_attribute a ON a.attrelid = conrelid AND a.attnum = k
                  WHERE a.attname = 'date'
              );
            IF cname IS NOT NULL THEN
                EXECUTE format('ALTER TABLE scheduled_reconciliations DROP CONSTRAINT %I', cname);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.create_unique_constraint("scheduled_reconciliations_date_key", "scheduled_reconciliations", ["date"])
