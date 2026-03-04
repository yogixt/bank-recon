import uuid

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BridgeMapping(Base):
    __tablename__ = "bridge_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    data_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    bank_id: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        Index("ix_bridge_ds_txn", "data_source_id", "transaction_id", unique=True),
    )
