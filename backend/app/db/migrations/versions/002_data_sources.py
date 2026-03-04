"""Add data_sources table and migrate bank_entries/bridge_mappings to use data_source_id

Revision ID: 002
Revises: 001
Create Date: 2026-03-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create data_sources table
    op.create_table(
        "data_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), server_default="uploading"),
        sa.Column("row_count", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. Modify bank_entries: add data_source_id, drop old session_id columns/indexes
    op.add_column("bank_entries", sa.Column("data_source_id", UUID(as_uuid=True), nullable=True))
    # Copy session_id to data_source_id for existing rows (backward compat during migration)
    op.execute("UPDATE bank_entries SET data_source_id = session_id")
    op.drop_index("ix_bank_entries_session_bank_id", table_name="bank_entries")
    op.drop_index("ix_bank_entries_session_id", table_name="bank_entries")
    op.drop_column("bank_entries", "session_id")
    op.alter_column("bank_entries", "data_source_id", nullable=False)
    op.create_index("ix_bank_entries_data_source_id", "bank_entries", ["data_source_id"])
    op.create_index("ix_bank_entries_ds_bank_id", "bank_entries", ["data_source_id", "bank_id"])

    # 3. Modify bridge_mappings: add data_source_id, drop old session_id columns/indexes
    op.add_column("bridge_mappings", sa.Column("data_source_id", UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE bridge_mappings SET data_source_id = session_id")
    op.drop_index("ix_bridge_session_txn", table_name="bridge_mappings")
    op.drop_index("ix_bridge_mappings_session_id", table_name="bridge_mappings")
    op.drop_column("bridge_mappings", "session_id")
    op.alter_column("bridge_mappings", "data_source_id", nullable=False)
    op.create_index("ix_bridge_mappings_data_source_id", "bridge_mappings", ["data_source_id"])
    op.create_index(
        "ix_bridge_ds_txn", "bridge_mappings",
        ["data_source_id", "transaction_id"], unique=True,
    )

    # 4. Modify reconciliation_sessions: remove file path columns, add source FKs
    op.add_column(
        "reconciliation_sessions",
        sa.Column("bank_source_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "reconciliation_sessions",
        sa.Column("bridge_source_id", UUID(as_uuid=True), nullable=True),
    )
    op.drop_column("reconciliation_sessions", "bank_statement_file")
    op.drop_column("reconciliation_sessions", "bank_statement_path")
    op.drop_column("reconciliation_sessions", "bridge_file")
    op.drop_column("reconciliation_sessions", "bridge_file_path")


def downgrade() -> None:
    # Restore reconciliation_sessions columns
    op.add_column("reconciliation_sessions", sa.Column("bridge_file_path", sa.Text))
    op.add_column("reconciliation_sessions", sa.Column("bridge_file", sa.String(512)))
    op.add_column("reconciliation_sessions", sa.Column("bank_statement_path", sa.Text))
    op.add_column("reconciliation_sessions", sa.Column("bank_statement_file", sa.String(512)))
    op.drop_column("reconciliation_sessions", "bridge_source_id")
    op.drop_column("reconciliation_sessions", "bank_source_id")

    # Restore bridge_mappings
    op.drop_index("ix_bridge_ds_txn", table_name="bridge_mappings")
    op.drop_index("ix_bridge_mappings_data_source_id", table_name="bridge_mappings")
    op.add_column("bridge_mappings", sa.Column("session_id", UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE bridge_mappings SET session_id = data_source_id")
    op.drop_column("bridge_mappings", "data_source_id")
    op.alter_column("bridge_mappings", "session_id", nullable=False)
    op.create_index("ix_bridge_mappings_session_id", "bridge_mappings", ["session_id"])
    op.create_index("ix_bridge_session_txn", "bridge_mappings", ["session_id", "transaction_id"], unique=True)

    # Restore bank_entries
    op.drop_index("ix_bank_entries_ds_bank_id", table_name="bank_entries")
    op.drop_index("ix_bank_entries_data_source_id", table_name="bank_entries")
    op.add_column("bank_entries", sa.Column("session_id", UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE bank_entries SET session_id = data_source_id")
    op.drop_column("bank_entries", "data_source_id")
    op.alter_column("bank_entries", "session_id", nullable=False)
    op.create_index("ix_bank_entries_session_id", "bank_entries", ["session_id"])
    op.create_index("ix_bank_entries_session_bank_id", "bank_entries", ["session_id", "bank_id"])

    # Drop data_sources table
    op.drop_table("data_sources")
