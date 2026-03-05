"""API endpoints for email ingestion management."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func, text

from app.api.deps import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("/logs")
async def get_ingestion_logs(
    page: int = 1,
    page_size: int = 50,
    email_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List email ingestion logs with pagination and filters."""
    conditions = []
    params: dict = {}
    if email_type:
        conditions.append("email_type = :email_type")
        params["email_type"] = email_type
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size

    count_q = text(f"SELECT COUNT(*) FROM email_ingestion_logs WHERE {where}")
    total_result = await db.execute(count_q, params)
    total = total_result.scalar() or 0

    query = text(
        f"""SELECT id, gmail_message_id, email_type, sender, subject,
            received_at, processed_at, attachment_filename, data_source_id,
            status, error_message
        FROM email_ingestion_logs WHERE {where}
        ORDER BY processed_at DESC
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


@router.get("/stats")
async def get_ingestion_stats(db: AsyncSession = Depends(get_db)):
    """Get ingestion statistics grouped by email type and status."""
    result = await db.execute(text(
        """SELECT email_type, status, COUNT(*) as count
        FROM email_ingestion_logs
        GROUP BY email_type, status
        ORDER BY email_type, status"""
    ))
    rows = result.mappings().all()

    stats: dict = {}
    for row in rows:
        et = row["email_type"]
        if et not in stats:
            stats[et] = {}
        stats[et][row["status"]] = row["count"]

    total = await db.execute(text("SELECT COUNT(*) FROM email_ingestion_logs"))

    return {
        "by_type": stats,
        "total": total.scalar() or 0,
    }


@router.post("/poll/bank-statement")
async def trigger_poll_bank_statement():
    """Manually trigger polling for bank statement emails."""
    from app.tasks.poll_inbox import poll_inbox_bank_statement_task
    result = poll_inbox_bank_statement_task.delay()
    return {"task_id": str(result.id), "message": "Bank statement poll triggered"}


@router.post("/poll/bridge-file")
async def trigger_poll_bridge_file():
    """Manually trigger polling for bridge file emails."""
    from app.tasks.poll_inbox import poll_inbox_bridge_file_task
    result = poll_inbox_bridge_file_task.delay()
    return {"task_id": str(result.id), "message": "Bridge file poll triggered"}


@router.post("/poll/lms-file")
async def trigger_poll_lms_file():
    """Manually trigger polling for LMS file emails."""
    from app.tasks.poll_inbox import poll_inbox_lms_file_task
    result = poll_inbox_lms_file_task.delay()
    return {"task_id": str(result.id), "message": "LMS file poll triggered"}
