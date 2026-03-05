"""API endpoints for LMS verification results."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter(prefix="/results", tags=["lms"])


@router.get("/{session_id}/lms-verification")
async def get_lms_verification(
    session_id: str,
    page: int = 1,
    page_size: int = 50,
    stage2_status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get LMS verification results for a session with pagination and filters."""
    conditions = ["session_id = :session_id"]
    params: dict = {"session_id": session_id}

    if stage2_status:
        conditions.append("stage2_status = :stage2_status")
        params["stage2_status"] = stage2_status
    if search:
        conditions.append("(transaction_id ILIKE :search OR bank_id ILIKE :search OR lms_trans_id ILIKE :search)")
        params["search"] = f"%{search}%"

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    count_q = text(f"SELECT COUNT(*) FROM lms_verification_results WHERE {where}")
    total_result = await db.execute(count_q, params)
    total = total_result.scalar() or 0

    query = text(
        f"""SELECT id, session_id, transaction_id, bank_id, lms_trans_id,
            stage1_status, stage2_status, bank_amount, lms_amount,
            lms_payment_ref, lms_txn_status, lms_utr_no, lms_bene_name,
            mismatch_details, verified_at
        FROM lms_verification_results WHERE {where}
        ORDER BY id
        LIMIT :limit OFFSET :offset"""
    )
    params["limit"] = page_size
    params["offset"] = offset
    result = await db.execute(query, params)
    rows = result.mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get("/{session_id}/lms-summary")
async def get_lms_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get LMS verification summary statistics for a session."""
    result = await db.execute(text(
        """SELECT stage2_status, COUNT(*) as count
        FROM lms_verification_results
        WHERE session_id = :session_id
        GROUP BY stage2_status"""
    ), {"session_id": session_id})
    rows = result.mappings().all()

    counts = {row["stage2_status"]: row["count"] for row in rows}
    total = sum(counts.values())

    stage1_matchable_result = await db.execute(
        text(
            """SELECT COUNT(*) AS count
            FROM reconciliation_results
            WHERE session_id = :session_id
              AND status IN ('MATCHED_SUCCESS', 'MATCHED_FAILED', 'REVERSAL')"""
        ),
        {"session_id": session_id},
    )
    stage1_matchable_total = int(stage1_matchable_result.scalar() or 0)

    return {
        "session_id": session_id,
        "total": total,
        "status_counts": counts,
        "stage1_matchable_total": stage1_matchable_total,
    }
