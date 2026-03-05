import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmailIngestionLog(Base):
    __tablename__ = "email_ingestion_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    gmail_message_id: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    email_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sender: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attachment_filename: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    data_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), server_default="processing")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_eil_gmid", "gmail_message_id"),
        Index("ix_eil_status", "status"),
    )
