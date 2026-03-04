import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReconciliationSession(Base):
    __tablename__ = "reconciliation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # References to permanent data sources
    bank_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    bridge_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Transaction IDs are still per-session
    transaction_ids_file: Mapped[str] = mapped_column(String(512), nullable=True)
    transaction_ids_path: Mapped[str] = mapped_column(Text, nullable=True)

    # Status: pending | parsing | reconciling | analyzing | completed | failed
    status: Mapped[str] = mapped_column(String(32), default="pending")

    # Statistics (populated after reconciliation)
    total_searched: Mapped[int] = mapped_column(Integer, default=0)
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    reversal_count: Mapped[int] = mapped_column(Integer, default=0)
    not_in_bridge_count: Mapped[int] = mapped_column(Integer, default=0)
    not_in_statement_count: Mapped[int] = mapped_column(Integer, default=0)
    total_success_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_failed_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_reversal_amount: Mapped[float] = mapped_column(Float, default=0.0)
    processing_time: Mapped[float] = mapped_column(Float, nullable=True)

    error_message: Mapped[str] = mapped_column(Text, nullable=True)
