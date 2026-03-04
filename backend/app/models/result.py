import uuid

from sqlalchemy import BigInteger, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    bank_id: Mapped[str] = mapped_column(String(128), nullable=True)
    date: Mapped[str] = mapped_column(String(64), nullable=True)
    debit_amount: Mapped[float] = mapped_column(Float, default=0.0)
    credit_amount: Mapped[float] = mapped_column(Float, default=0.0)
    # MATCHED_SUCCESS, MATCHED_FAILED, NOT_IN_BRIDGE, NOT_IN_STATEMENT, FUZZY_MATCH, DUPLICATE
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(256), nullable=True)
    branch: Mapped[str] = mapped_column(String(256), nullable=True)
    reference_no: Mapped[str] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    error_type: Mapped[str] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_results_session_status", "session_id", "status"),
        Index("ix_results_session_txn", "session_id", "transaction_id"),
    )
