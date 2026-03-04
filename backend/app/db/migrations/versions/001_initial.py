"""Initial schema with pg_trgm

Revision ID: 001
Revises: None
Create Date: 2026-03-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm for fuzzy matching
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # reconciliation_sessions
    op.create_table(
        "reconciliation_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("bank_statement_file", sa.String(512)),
        sa.Column("bridge_file", sa.String(512)),
        sa.Column("transaction_ids_file", sa.String(512)),
        sa.Column("bank_statement_path", sa.Text),
        sa.Column("bridge_file_path", sa.Text),
        sa.Column("transaction_ids_path", sa.Text),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("total_searched", sa.Integer, server_default="0"),
        sa.Column("total_found", sa.Integer, server_default="0"),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("failed_count", sa.Integer, server_default="0"),
        sa.Column("not_in_bridge_count", sa.Integer, server_default="0"),
        sa.Column("not_in_statement_count", sa.Integer, server_default="0"),
        sa.Column("total_success_amount", sa.Float, server_default="0.0"),
        sa.Column("total_failed_amount", sa.Float, server_default="0.0"),
        sa.Column("processing_time", sa.Float),
        sa.Column("error_message", sa.Text),
    )

    # bank_entries
    op.create_table(
        "bank_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("bank_id", sa.String(128)),
        sa.Column("date", sa.String(64)),
        sa.Column("description", sa.Text),
        sa.Column("debit_amount", sa.Float, server_default="0.0"),
        sa.Column("credit_amount", sa.Float, server_default="0.0"),
        sa.Column("branch", sa.String(256)),
        sa.Column("reference_no", sa.String(128)),
        sa.Column("customer_name", sa.String(256)),
    )
    op.create_index("ix_bank_entries_session_id", "bank_entries", ["session_id"])
    op.create_index("ix_bank_entries_session_bank_id", "bank_entries", ["session_id", "bank_id"])
    # GIN trigram index for fuzzy matching
    op.execute(
        "CREATE INDEX ix_bank_entries_bank_id_trgm ON bank_entries "
        "USING GIN (bank_id gin_trgm_ops)"
    )

    # bridge_mappings
    op.create_table(
        "bridge_mappings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("bank_id", sa.String(128), nullable=False),
    )
    op.create_index("ix_bridge_mappings_session_id", "bridge_mappings", ["session_id"])
    op.create_index("ix_bridge_session_txn", "bridge_mappings", ["session_id", "transaction_id"], unique=True)

    # transaction_ids
    op.create_table(
        "transaction_ids",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
    )
    op.create_index("ix_transaction_ids_session_id", "transaction_ids", ["session_id"])
    op.create_index("ix_txn_session_txn", "transaction_ids", ["session_id", "transaction_id"])

    # reconciliation_results
    op.create_table(
        "reconciliation_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("bank_id", sa.String(128)),
        sa.Column("date", sa.String(64)),
        sa.Column("debit_amount", sa.Float, server_default="0.0"),
        sa.Column("credit_amount", sa.Float, server_default="0.0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("customer_name", sa.String(256)),
        sa.Column("branch", sa.String(256)),
        sa.Column("reference_no", sa.String(128)),
        sa.Column("description", sa.Text),
        sa.Column("error_type", sa.Text),
    )
    op.create_index("ix_results_session_id", "reconciliation_results", ["session_id"])
    op.create_index("ix_results_session_status", "reconciliation_results", ["session_id", "status"])
    op.create_index("ix_results_session_txn", "reconciliation_results", ["session_id", "transaction_id"])

    # anomalies
    op.create_table(
        "anomalies",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("anomaly_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), server_default="medium"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("transaction_id", sa.String(128)),
        sa.Column("bank_id", sa.String(128)),
        sa.Column("amount", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_anomalies_session_id", "anomalies", ["session_id"])

    # tasks
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("message", sa.Text),
        sa.Column("celery_task_id", sa.String(256)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tasks_session_id", "tasks", ["session_id"])


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("anomalies")
    op.drop_table("reconciliation_results")
    op.drop_table("transaction_ids")
    op.drop_table("bridge_mappings")
    op.drop_table("bank_entries")
    op.drop_table("reconciliation_sessions")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
