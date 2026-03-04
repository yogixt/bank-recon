"""Endpoints: start reconciliation + get status."""

import uuid

from celery import chain
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.data_source import DataSource
from app.models.session import ReconciliationSession
from app.models.task import Task
from app.schemas.schemas import ReconcileRequest, ReconcileResponse, TaskStatusOut
from app.tasks.parse_transactions import parse_transactions
from app.tasks.run_reconciliation import run_reconciliation_task
from app.tasks.run_ai_analysis import run_ai_analysis

router = APIRouter()


@router.post("/reconcile", response_model=ReconcileResponse)
async def start_reconciliation(
    req: ReconcileRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReconciliationSession).where(ReconciliationSession.id == req.session_id)
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    if not sess.transaction_ids_path:
        raise HTTPException(status_code=400, detail="Transaction IDs must be uploaded first")

    # Validate bank source
    bank_result = await db.execute(
        select(DataSource).where(
            DataSource.id == req.bank_source_id,
            DataSource.source_type == "bank_statement",
            DataSource.status == "ready",
        )
    )
    if not bank_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Bank statement data source not found or not ready")

    # Validate bridge source
    bridge_result = await db.execute(
        select(DataSource).where(
            DataSource.id == req.bridge_source_id,
            DataSource.source_type == "bridge_file",
            DataSource.status == "ready",
        )
    )
    if not bridge_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Bridge file data source not found or not ready")

    # Store source references on session
    sess.bank_source_id = req.bank_source_id
    sess.bridge_source_id = req.bridge_source_id
    sess.status = "parsing"
    await db.flush()

    sid = str(sess.id)

    # Create task records for tracking (only parse_transactions + reconciliation + ai_analysis)
    task_types = ["parse_transactions", "reconciliation", "ai_analysis"]
    orchestration_task_id = uuid.uuid4()
    for tt in task_types:
        t = Task(session_id=sess.id, task_type=tt, status="pending")
        db.add(t)
    await db.commit()

    # Dispatch Celery: parse txn IDs → reconcile → AI analysis
    parse_txns = parse_transactions.si(sid, sess.transaction_ids_path)
    recon = run_reconciliation_task.si(sid)
    ai = run_ai_analysis.si(sid)

    workflow = chain(parse_txns, recon, ai)
    workflow.apply_async()

    return ReconcileResponse(
        session_id=sess.id,
        task_id=orchestration_task_id,
        message="Reconciliation started: parsing transaction IDs, then reconciling with stored data sources",
    )


@router.get("/reconcile/status/{session_id}")
async def get_status(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    # Get session
    result = await db.execute(
        select(ReconciliationSession).where(ReconciliationSession.id == session_id)
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get tasks
    task_result = await db.execute(
        select(Task).where(Task.session_id == session_id)
    )
    tasks = task_result.scalars().all()

    return {
        "session_id": str(sess.id),
        "session_status": sess.status,
        "tasks": [
            {
                "task_type": t.task_type,
                "status": t.status,
                "progress": t.progress,
                "message": t.message,
            }
            for t in tasks
        ],
    }
