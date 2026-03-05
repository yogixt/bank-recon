"""Create missing LMS tables on upgraded deployments.

Revision ID: 005_backfill_lms_tables
Revises: 004_add_lms_schedule_columns
Create Date: 2026-03-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "005_backfill_lms_tables"
down_revision: Union[str, None] = "004_add_lms_schedule_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lms_entries (
            id BIGSERIAL PRIMARY KEY,
            data_source_id UUID NOT NULL,
            user_id INTEGER,
            mobile_number VARCHAR(20),
            role_name VARCHAR(64),
            point DOUBLE PRECISION DEFAULT 0,
            amount DOUBLE PRECISION DEFAULT 0,
            created_on TIMESTAMPTZ,
            description TEXT,
            last_updated_on TIMESTAMPTZ,
            trans_id VARCHAR(128) NOT NULL,
            withdraw_type VARCHAR(32),
            state_name VARCHAR(128),
            payment_ref_no VARCHAR(64),
            txn_status VARCHAR(32),
            utr_no VARCHAR(64),
            bene_name VARCHAR(256),
            ifsc_code VARCHAR(20),
            credit_acc_no VARCHAR(64),
            od_amount DOUBLE PRECISION,
            reference_no VARCHAR(128),
            txn_reference_no VARCHAR(64)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_lms_tid ON lms_entries (data_source_id, trans_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_lms_pref ON lms_entries (data_source_id, payment_ref_no)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lms_verification_results (
            id BIGSERIAL PRIMARY KEY,
            session_id UUID NOT NULL,
            transaction_id VARCHAR(256),
            bank_id VARCHAR(256),
            lms_trans_id VARCHAR(128),
            stage1_status VARCHAR(32),
            stage2_status VARCHAR(32),
            bank_amount DOUBLE PRECISION,
            lms_amount DOUBLE PRECISION,
            lms_payment_ref VARCHAR(64),
            lms_txn_status VARCHAR(32),
            lms_utr_no VARCHAR(64),
            lms_bene_name VARCHAR(256),
            mismatch_details TEXT,
            verified_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_lvr_sess ON lms_verification_results (session_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_lvr_s2 ON lms_verification_results (session_id, stage2_status)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lms_verification_results")
    op.execute("DROP TABLE IF EXISTS lms_entries")
