import uuid

from sqlalchemy import BigInteger, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BankEntry(Base):
    __tablename__ = "bank_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    data_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    bank_id: Mapped[str] = mapped_column(String(128), nullable=True)
    date: Mapped[str] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    debit_amount: Mapped[float] = mapped_column(Float, default=0.0)
    credit_amount: Mapped[float] = mapped_column(Float, default=0.0)
    branch: Mapped[str] = mapped_column(String(256), nullable=True)
    reference_no: Mapped[str] = mapped_column(String(128), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        Index("ix_bank_entries_ds_bank_id", "data_source_id", "bank_id"),
        # GIN trigram index created in migration (requires pg_trgm extension)
    )
