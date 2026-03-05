import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LmsVerificationResult(Base):
    __tablename__ = "lms_verification_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    bank_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    lms_trans_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    stage1_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    stage2_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    bank_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lms_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lms_payment_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lms_txn_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    lms_utr_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lms_bene_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    mismatch_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_lvr_sess", "session_id"),
        Index("ix_lvr_s2", "session_id", "stage2_status"),
    )
