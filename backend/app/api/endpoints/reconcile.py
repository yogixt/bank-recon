"""Endpoints: start reconciliation + get status."""

import uuid
from datetime import date

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
from app.tasks.auto_reconcile import run_lms_verification_task
from app.services.time_utils import today_ist

router = APIRouter()


def _covers_target_date(ds: DataSource, target_date: date) -> bool:
    if not ds.data_date_from and not ds.data_date_to:
        return False
    if ds.data_date_from and ds.data_date_from > target_date:
        return False
    if ds.data_date_to and ds.data_date_to < target_date:
        return False
    return True


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
    bank_ds = bank_result.scalar_one_or_none()
    if not bank_ds:
        raise HTTPException(status_code=400, detail="Bank statement data source not found or not ready")

    # Validate bridge source
    bridge_result = await db.execute(
        select(DataSource).where(
            DataSource.id == req.bridge_source_id,
            DataSource.source_type == "bridge_file",
            DataSource.status == "ready",
        )
    )
    bridge_ds = bridge_result.scalar_one_or_none()
    if not bridge_ds:
        raise HTTPException(status_code=400, detail="Bridge file data source not found or not ready")

    target_date = today_ist()
    if not _covers_target_date(bank_ds, target_date):
        raise HTTPException(
            status_code=400,
            detail=f"Bank statement internal date does not cover {target_date.isoformat()}",
        )
    if not _covers_target_date(bridge_ds, target_date):
        raise HTTPException(
            status_code=400,
            detail=f"Bridge file internal date does not cover {target_date.isoformat()}",
        )

    # Store source references on session
    sess.bank_source_id = req.bank_source_id
    sess.bridge_source_id = req.bridge_source_id
    sess.status = "parsing"
    await db.flush()

    sid = str(sess.id)

    # Optional Stage 2: pick latest ready LMS source automatically
    lms_result = await db.execute(
        select(DataSource.id)
        .where(
            DataSource.source_type == "lms_file",
            DataSource.status == "ready",
            DataSource.data_date_from <= target_date,
            DataSource.data_date_to >= target_date,
        )
        .order_by(DataSource.created_at.desc())
        .limit(1)
    )
    lms_source_id = lms_result.scalar_one_or_none()

    # Create task records for tracking (only parse_transactions + reconciliation + ai_analysis)
    task_types = ["parse_transactions", "reconciliation", "ai_analysis"]
    if lms_source_id:
        task_types.append("lms_verification")
    orchestration_task_id = uuid.uuid4()
    for tt in task_types:
        t = Task(session_id=sess.id, task_type=tt, status="pending")
        db.add(t)
    await db.commit()

    # Dispatch Celery: parse txn IDs → reconcile → AI analysis
    parse_txns = parse_transactions.si(sid, sess.transaction_ids_path)
    recon = run_reconciliation_task.si(sid)
    ai = run_ai_analysis.si(sid)

    if lms_source_id:
        lms = run_lms_verification_task.si(sid, str(lms_source_id))
        workflow = chain(parse_txns, recon, ai, lms)
    else:
        workflow = chain(parse_txns, recon, ai)
    workflow.apply_async()

    return ReconcileResponse(
        session_id=sess.id,
        task_id=orchestration_task_id,
        message=(
            "Reconciliation started: parsing transaction IDs, then reconciling with stored data sources"
            + (" and running LMS verification" if lms_source_id else "")
        ),
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
