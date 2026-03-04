from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# -- Data Source --
class DataSourceCreate(BaseModel):
    name: str
    source_type: str  # 'bank_statement' | 'bridge_file'


class DataSourceOut(BaseModel):
    id: UUID
    name: str
    source_type: str
    filename: str
    status: str
    row_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DataSourceUploadResponse(BaseModel):
    data_source_id: UUID
    name: str
    source_type: str
    filename: str
    message: str


# -- Session --
class SessionCreate(BaseModel):
    pass


class SessionOut(BaseModel):
    id: UUID
    created_at: datetime
    status: str
    bank_source_id: Optional[UUID] = None
    bridge_source_id: Optional[UUID] = None
    transaction_ids_file: Optional[str] = None
    total_searched: int = 0
    total_found: int = 0
    success_count: int = 0
    failed_count: int = 0
    reversal_count: int = 0
    not_in_bridge_count: int = 0
    not_in_statement_count: int = 0
    total_success_amount: float = 0.0
    total_failed_amount: float = 0.0
    total_reversal_amount: float = 0.0
    processing_time: Optional[float] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


# -- Upload --
class UploadResponse(BaseModel):
    session_id: UUID
    file_type: str
    filename: str
    message: str


# -- Reconcile --
class ReconcileRequest(BaseModel):
    session_id: UUID
    bank_source_id: UUID
    bridge_source_id: UUID


class ReconcileResponse(BaseModel):
    session_id: UUID
    task_id: UUID
    message: str


class TaskStatusOut(BaseModel):
    id: UUID
    session_id: UUID
    task_type: str
    status: str
    progress: int
    message: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


# -- Results --
class ResultRow(BaseModel):
    id: int
    transaction_id: str
    bank_id: Optional[str] = None
    date: Optional[str] = None
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    status: str
    customer_name: Optional[str] = None
    branch: Optional[str] = None
    reference_no: Optional[str] = None
    description: Optional[str] = None
    error_type: Optional[str] = None

    model_config = {"from_attributes": True}


class PaginatedResults(BaseModel):
    items: list[ResultRow]
    total: int
    page: int
    page_size: int
    total_pages: int


class SummaryOut(BaseModel):
    session: SessionOut
    status_counts: dict[str, int]


# -- Anomaly --
class AnomalyOut(BaseModel):
    id: int
    anomaly_type: str
    severity: str
    description: str
    transaction_id: Optional[str] = None
    bank_id: Optional[str] = None
    amount: Optional[float] = None

    model_config = {"from_attributes": True}


# -- Chat --
class ChatRequest(BaseModel):
    session_id: UUID
    message: str


class ChatResponse(BaseModel):
    response: str
