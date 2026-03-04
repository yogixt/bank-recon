import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    # duplicate_bank_id, suspicious_amount, date_outlier, orphan_bridge, mismatched_status
    anomaly_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # low, medium, high
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(128), nullable=True)
    bank_id: Mapped[str] = mapped_column(String(128), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
