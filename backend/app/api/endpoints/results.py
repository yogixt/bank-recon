"""Results endpoints: summary, paginated transactions, CSV download, anomalies."""

import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.constants import CSV_STREAM_BATCH
from app.models.anomaly import Anomaly
from app.models.result import ReconciliationResult
from app.models.session import ReconciliationSession
from app.schemas.schemas import AnomalyOut, PaginatedResults, ResultRow, SummaryOut, SessionOut
from app.services.notification import send_reconciliation_notification

router = APIRouter()


@router.get("/results/{session_id}/summary", response_model=SummaryOut)
async def get_summary(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ReconciliationSession).where(ReconciliationSession.id == session_id)
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Status breakdown
    counts_result = await db.execute(
        select(ReconciliationResult.status, func.count())
        .where(ReconciliationResult.session_id == session_id)
        .group_by(ReconciliationResult.status)
    )
    status_counts = {row[0]: row[1] for row in counts_result.all()}

    return SummaryOut(session=SessionOut.model_validate(sess), status_counts=status_counts)


@router.get("/results/{session_id}/transactions", response_model=PaginatedResults)
async def get_transactions(
    session_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = None,
    search: str | None = None,
    branch: str | None = None,
    customer_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    base_q = select(ReconciliationResult).where(
        ReconciliationResult.session_id == session_id
    )
    count_q = select(func.count()).select_from(ReconciliationResult).where(
        ReconciliationResult.session_id == session_id
    )

    if status:
        base_q = base_q.where(ReconciliationResult.status == status)
        count_q = count_q.where(ReconciliationResult.status == status)
    if search:
        like = f"%{search.upper()}%"
        base_q = base_q.where(
            ReconciliationResult.transaction_id.ilike(like)
            | ReconciliationResult.bank_id.ilike(like)
        )
        count_q = count_q.where(
            ReconciliationResult.transaction_id.ilike(like)
            | ReconciliationResult.bank_id.ilike(like)
        )
    if branch:
        branch_like = f"%{branch}%"
        base_q = base_q.where(ReconciliationResult.branch.ilike(branch_like))
        count_q = count_q.where(ReconciliationResult.branch.ilike(branch_like))
    if customer_name:
        cust_like = f"%{customer_name}%"
        base_q = base_q.where(ReconciliationResult.customer_name.ilike(cust_like))
        count_q = count_q.where(ReconciliationResult.customer_name.ilike(cust_like))
    if date_from:
        base_q = base_q.where(ReconciliationResult.date >= date_from)
        count_q = count_q.where(ReconciliationResult.date >= date_from)
    if date_to:
        base_q = base_q.where(ReconciliationResult.date <= date_to)
        count_q = count_q.where(ReconciliationResult.date <= date_to)
    if min_amount is not None:
        base_q = base_q.where(
            (ReconciliationResult.debit_amount >= min_amount)
            | (ReconciliationResult.credit_amount >= min_amount)
        )
        count_q = count_q.where(
            (ReconciliationResult.debit_amount >= min_amount)
            | (ReconciliationResult.credit_amount >= min_amount)
        )
    if max_amount is not None:
        base_q = base_q.where(
            (ReconciliationResult.debit_amount <= max_amount)
            & (ReconciliationResult.credit_amount <= max_amount)
        )
        count_q = count_q.where(
            (ReconciliationResult.debit_amount <= max_amount)
            & (ReconciliationResult.credit_amount <= max_amount)
        )

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    offset = (page - 1) * page_size
    rows_result = await db.execute(
        base_q.order_by(ReconciliationResult.id).offset(offset).limit(page_size)
    )
    items = [ResultRow.model_validate(r) for r in rows_result.scalars().all()]

    return PaginatedResults(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/results/{session_id}/download")
async def download_csv(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Stream CSV download without loading all rows into memory."""

    # Verify session exists
    result = await db.execute(
        select(ReconciliationSession.id).where(ReconciliationSession.id == session_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    async def generate():
        # Header
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Transaction ID", "Bank ID", "Date", "Debit Amount", "Credit Amount",
            "Status", "Customer Name", "Branch", "Reference No", "Description", "Error",
        ])
        yield buf.getvalue()

        # Stream rows in batches
        offset = 0
        while True:
            rows_result = await db.execute(
                select(ReconciliationResult)
                .where(ReconciliationResult.session_id == session_id)
                .order_by(ReconciliationResult.id)
                .offset(offset)
                .limit(CSV_STREAM_BATCH)
            )
            rows = rows_result.scalars().all()
            if not rows:
                break

            buf = io.StringIO()
            writer = csv.writer(buf)
            for r in rows:
                writer.writerow([
                    r.transaction_id, r.bank_id or "N/A", r.date or "N/A",
                    r.debit_amount, r.credit_amount, r.status,
                    r.customer_name or "N/A", r.branch or "N/A",
                    r.reference_no or "N/A", r.description or "N/A",
                    r.error_type or "",
                ])
            yield buf.getvalue()
            offset += CSV_STREAM_BATCH

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=reconciliation_{session_id}.csv"},
    )


@router.get("/results/{session_id}/anomalies", response_model=list[AnomalyOut])
async def get_anomalies(
    session_id: uuid.UUID,
    include_low: bool = False,
    db: AsyncSession = Depends(get_db),
):
    severity_rank = case(
        (Anomaly.severity == "high", 0),
        (Anomaly.severity == "medium", 1),
        (Anomaly.severity == "low", 2),
        else_=3,
    )

    query = select(Anomaly).where(Anomaly.session_id == session_id)
    if not include_low:
        query = query.where(Anomaly.severity.in_(["high", "medium"]))

    result = await db.execute(query.order_by(severity_rank, Anomaly.id))
    return [AnomalyOut.model_validate(a) for a in result.scalars().all()]


@router.post("/results/{session_id}/send-audit-report")
async def send_audit_report(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually send the detailed audit report email for a completed session."""
    session_result = await db.execute(
        select(ReconciliationSession).where(ReconciliationSession.id == session_id)
    )
    sess = session_result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    stage1_stats = {
        "total_searched": sess.total_searched,
        "total_found": sess.total_found,
        "success_count": sess.success_count,
        "failed_count": sess.failed_count,
        "reversal_count": sess.reversal_count,
        "not_in_bridge": sess.not_in_bridge_count,
        "not_in_statement": sess.not_in_statement_count,
        "total_success_amount": sess.total_success_amount,
        "total_failed_amount": sess.total_failed_amount,
        "total_reversal_amount": sess.total_reversal_amount,
    }

    stage2_result = await db.execute(
        text(
            """SELECT stage2_status, COUNT(*) AS count
            FROM lms_verification_results
            WHERE session_id = :session_id
            GROUP BY stage2_status"""
        ),
        {"session_id": str(session_id)},
    )
    stage2_rows = stage2_result.mappings().all()
    stage2_stats = {row["stage2_status"]: int(row["count"]) for row in stage2_rows}
    if stage2_stats:
        stage2_stats["total"] = sum(stage2_stats.values())

    recon_date_result = await db.execute(
        text(
            """SELECT date
            FROM scheduled_reconciliations
            WHERE session_id = :session_id
            ORDER BY date DESC
            LIMIT 1"""
        ),
        {"session_id": str(session_id)},
    )
    recon_date = recon_date_result.scalar()

    delivery = send_reconciliation_notification(
        stage1_stats=stage1_stats,
        stage2_stats=stage2_stats if stage2_stats else None,
        session_id=str(session_id),
        recon_date=recon_date.isoformat() if recon_date else "",
        include_audit_report=True,
    )

    if not delivery.get("sent") and delivery.get("failed"):
        raise HTTPException(status_code=502, detail=f"Email sending failed: {delivery['failed']}")

    return {
        "message": "Detailed audit report email sent",
        "session_id": str(session_id),
        "sent": delivery.get("sent", []),
        "failed": delivery.get("failed", []),
    }
