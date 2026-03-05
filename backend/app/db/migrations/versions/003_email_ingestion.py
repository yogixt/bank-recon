"""v5.0: Email ingestion, LMS entries, scheduled reconciliations, LMS verification

Revision ID: 003_email_ingestion
Revises: c8515d369ff9
Create Date: 2026-03-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_email_ingestion"
down_revision: Union[str, None] = "c8515d369ff9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_ingestion_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("gmail_message_id", sa.String(256), unique=True, nullable=False),
        sa.Column("email_type", sa.String(32), nullable=False),
        sa.Column("sender", sa.String(512)),
        sa.Column("subject", sa.Text),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("attachment_filename", sa.String(512)),
        sa.Column("data_source_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(32), server_default="processing"),
        sa.Column("error_message", sa.Text),
    )
    op.create_index("ix_eil_gmid", "email_ingestion_logs", ["gmail_message_id"])
    op.create_index("ix_eil_status", "email_ingestion_logs", ["status"])

    op.create_table(
        "scheduled_reconciliations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date, unique=True, nullable=False),
        sa.Column("bank_source_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("bridge_source_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("lms_source_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(32), server_default="waiting_sources"),
        sa.Column("bank_ingested_at", sa.DateTime(timezone=True)),
        sa.Column("bridge_ingested_at", sa.DateTime(timezone=True)),
        sa.Column("lms_ingested_at", sa.DateTime(timezone=True)),
        sa.Column("triggered_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sr_date", "scheduled_reconciliations", ["date"])

    op.create_table(
        "lms_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("data_source_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer),
        sa.Column("mobile_number", sa.String(20)),
        sa.Column("role_name", sa.String(64)),
        sa.Column("point", sa.Float, server_default="0"),
        sa.Column("amount", sa.Float, server_default="0"),
        sa.Column("created_on", sa.DateTime(timezone=True)),
        sa.Column("description", sa.Text),
        sa.Column("last_updated_on", sa.DateTime(timezone=True)),
        sa.Column("trans_id", sa.String(128), nullable=False),
        sa.Column("withdraw_type", sa.String(32)),
        sa.Column("state_name", sa.String(128)),
        sa.Column("payment_ref_no", sa.String(64)),
        sa.Column("txn_status", sa.String(32)),
        sa.Column("utr_no", sa.String(64)),
        sa.Column("bene_name", sa.String(256)),
        sa.Column("ifsc_code", sa.String(20)),
        sa.Column("credit_acc_no", sa.String(64)),
        sa.Column("od_amount", sa.Float),
        sa.Column("reference_no", sa.String(128)),
        sa.Column("txn_reference_no", sa.String(64)),
    )
    op.create_index("ix_lms_tid", "lms_entries", ["data_source_id", "trans_id"])
    op.create_index("ix_lms_pref", "lms_entries", ["data_source_id", "payment_ref_no"])

    op.create_table(
        "lms_verification_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", sa.String(256)),
        sa.Column("bank_id", sa.String(256)),
        sa.Column("lms_trans_id", sa.String(128)),
        sa.Column("stage1_status", sa.String(32)),
        sa.Column("stage2_status", sa.String(32)),
        sa.Column("bank_amount", sa.Float),
        sa.Column("lms_amount", sa.Float),
        sa.Column("lms_payment_ref", sa.String(64)),
        sa.Column("lms_txn_status", sa.String(32)),
        sa.Column("lms_utr_no", sa.String(64)),
        sa.Column("lms_bene_name", sa.String(256)),
        sa.Column("mismatch_details", sa.Text),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lvr_sess", "lms_verification_results", ["session_id"])
    op.create_index("ix_lvr_s2", "lms_verification_results", ["session_id", "stage2_status"])


def downgrade() -> None:
    op.drop_table("lms_verification_results")
    op.drop_table("lms_entries")
    op.drop_table("scheduled_reconciliations")
    op.drop_table("email_ingestion_logs")
