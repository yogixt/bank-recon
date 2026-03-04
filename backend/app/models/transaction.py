import uuid

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TransactionId(Base):
    __tablename__ = "transaction_ids"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("ix_txn_session_txn", "session_id", "transaction_id"),
    )
