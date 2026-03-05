import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LmsEntry(Base):
    __tablename__ = "lms_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    data_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mobile_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    point: Mapped[float] = mapped_column(Float, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0)
    created_on: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_updated_on: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trans_id: Mapped[str] = mapped_column(String(128), nullable=False)
    withdraw_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    state_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # Parsed from description JSON (Bank rows only)
    payment_ref_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    txn_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    utr_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bene_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    ifsc_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    credit_acc_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    od_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_no: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    txn_reference_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_lms_tid", "data_source_id", "trans_id"),
        Index("ix_lms_pref", "data_source_id", "payment_ref_no"),
    )
