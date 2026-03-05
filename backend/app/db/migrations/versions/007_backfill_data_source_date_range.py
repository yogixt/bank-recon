"""Backfill data source internal date ranges from parsed records.

Revision ID: 007_ds_date_range_backfill
Revises: 006_add_data_source_date_range
Create Date: 2026-03-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007_ds_date_range_backfill"
down_revision: Union[str, None] = "006_add_data_source_date_range"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bank statement date range from parsed bank entries.
    op.execute(
        """
        UPDATE data_sources ds
        SET data_date_from = src.min_date,
            data_date_to = src.max_date
        FROM (
            SELECT data_source_id, MIN(date::date) AS min_date, MAX(date::date) AS max_date
            FROM bank_entries
            WHERE date IS NOT NULL
            GROUP BY data_source_id
        ) src
        WHERE ds.id = src.data_source_id
          AND ds.source_type = 'bank_statement'
          AND (ds.data_date_from IS NULL OR ds.data_date_to IS NULL)
        """
    )

    # Bridge date range from transaction IDs that embed YYYYMMDD.
    op.execute(
        """
        UPDATE data_sources ds
        SET data_date_from = src.min_date,
            data_date_to = src.max_date
        FROM (
            SELECT
                data_source_id,
                MIN(CASE
                    WHEN substring(transaction_id from '(20[0-9]{6})') IS NOT NULL
                    THEN to_date(substring(transaction_id from '(20[0-9]{6})'), 'YYYYMMDD')
                    ELSE NULL
                END) AS min_date,
                MAX(CASE
                    WHEN substring(transaction_id from '(20[0-9]{6})') IS NOT NULL
                    THEN to_date(substring(transaction_id from '(20[0-9]{6})'), 'YYYYMMDD')
                    ELSE NULL
                END) AS max_date
            FROM bridge_mappings
            GROUP BY data_source_id
        ) src
        WHERE ds.id = src.data_source_id
          AND ds.source_type = 'bridge_file'
          AND src.min_date IS NOT NULL
          AND src.max_date IS NOT NULL
          AND (ds.data_date_from IS NULL OR ds.data_date_to IS NULL)
        """
    )

    # LMS date range from created_on, fallback to date in trans_id.
    op.execute(
        """
        UPDATE data_sources ds
        SET data_date_from = src.min_date,
            data_date_to = src.max_date
        FROM (
            SELECT
                data_source_id,
                MIN(
                    COALESCE(
                        created_on::date,
                        CASE
                            WHEN substring(trans_id from '(20[0-9]{6})') IS NOT NULL
                            THEN to_date(substring(trans_id from '(20[0-9]{6})'), 'YYYYMMDD')
                            ELSE NULL
                        END
                    )
                ) AS min_date,
                MAX(
                    COALESCE(
                        created_on::date,
                        CASE
                            WHEN substring(trans_id from '(20[0-9]{6})') IS NOT NULL
                            THEN to_date(substring(trans_id from '(20[0-9]{6})'), 'YYYYMMDD')
                            ELSE NULL
                        END
                    )
                ) AS max_date
            FROM lms_entries
            GROUP BY data_source_id
        ) src
        WHERE ds.id = src.data_source_id
          AND ds.source_type = 'lms_file'
          AND src.min_date IS NOT NULL
          AND src.max_date IS NOT NULL
          AND (ds.data_date_from IS NULL OR ds.data_date_to IS NULL)
        """
    )


def downgrade() -> None:
    # Keep downgrade non-destructive for already populated rows.
    pass
