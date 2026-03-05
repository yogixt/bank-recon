"""API endpoints for scheduled reconciliation management."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_db
from app.services.time_utils import today_ist

router = APIRouter(prefix="/schedules", tags=["schedules"])


class CreateScheduleRequest(BaseModel):
    date: str  # YYYY-MM-DD
    bank_source_id: Optional[str] = None
    bridge_source_id: Optional[str] = None
    lms_source_id: Optional[str] = None


def _covers_target_date(data_date_from, data_date_to, target_date) -> bool:
    if not data_date_from and not data_date_to:
        return False
    if data_date_from and data_date_from > target_date:
        return False
    if data_date_to and data_date_to < target_date:
        return False
    return True


@router.get("")
async def list_schedules(
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """List scheduled reconciliations with pagination."""
    offset = (page - 1) * page_size
    total_result = await db.execute(text("SELECT COUNT(*) FROM scheduled_reconciliations"))
    total = total_result.scalar() or 0

    result = await db.execute(text(
        """SELECT sr.id, sr.date, sr.bank_source_id, sr.bridge_source_id, sr.lms_source_id,
            sr.session_id, sr.status, sr.bank_ingested_at, sr.bridge_ingested_at,
            sr.lms_ingested_at, sr.triggered_at, sr.completed_at, sr.error_message, sr.created_at,
            b.data_date_from AS bank_data_date_from, b.data_date_to AS bank_data_date_to,
            br.data_date_from AS bridge_data_date_from, br.data_date_to AS bridge_data_date_to,
            l.data_date_from AS lms_data_date_from, l.data_date_to AS lms_data_date_to
        FROM scheduled_reconciliations sr
        LEFT JOIN data_sources b ON b.id = sr.bank_source_id
        LEFT JOIN data_sources br ON br.id = sr.bridge_source_id
        LEFT JOIN data_sources l ON l.id = sr.lms_source_id
        ORDER BY sr.date DESC
        LIMIT :limit OFFSET :offset"""
    ), {"limit": page_size, "offset": offset})
    rows = result.mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get("/today")
async def get_today_schedule(db: AsyncSession = Depends(get_db)):
    """Get today's schedule status."""
    today = today_ist()
    result = await db.execute(text(
        """SELECT sr.id, sr.date, sr.bank_source_id, sr.bridge_source_id, sr.lms_source_id,
            sr.session_id, sr.status, sr.bank_ingested_at, sr.bridge_ingested_at,
            sr.lms_ingested_at, sr.triggered_at, sr.completed_at, sr.error_message, sr.created_at,
            b.data_date_from AS bank_data_date_from, b.data_date_to AS bank_data_date_to,
            br.data_date_from AS bridge_data_date_from, br.data_date_to AS bridge_data_date_to,
            l.data_date_from AS lms_data_date_from, l.data_date_to AS lms_data_date_to
        FROM scheduled_reconciliations sr
        LEFT JOIN data_sources b ON b.id = sr.bank_source_id
        LEFT JOIN data_sources br ON br.id = sr.bridge_source_id
        LEFT JOIN data_sources l ON l.id = sr.lms_source_id
        WHERE sr.date = :today"""
    ), {"today": today})
    row = result.mappings().first()
    if not row:
        return {"exists": False, "date": today.isoformat()}
    return {"exists": True, **dict(row)}


@router.post("")
async def create_schedule(body: CreateScheduleRequest, db: AsyncSession = Depends(get_db)):
    """Create a new scheduled reconciliation for a given date."""
    from datetime import date as date_type
    try:
        target_date = date_type.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Check if schedule already exists for this date
    existing = await db.execute(
        text("SELECT id FROM scheduled_reconciliations WHERE date = :d"),
        {"d": target_date},
    )
    if existing.first():
        raise HTTPException(status_code=409, detail=f"Schedule already exists for {target_date}")

    # Validate sources exist and are ready, if provided
    now = datetime.utcnow()
    source_ids = {
        "bank": body.bank_source_id,
        "bridge": body.bridge_source_id,
        "lms": body.lms_source_id,
    }
    for label, src_id in source_ids.items():
        if src_id:
            r = await db.execute(
                text("SELECT id, status FROM data_sources WHERE id = :id"),
                {"id": src_id},
            )
            row = r.mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail=f"{label} source not found")
            if row["status"] != "ready":
                raise HTTPException(status_code=400, detail=f"{label} source is not ready (status: {row['status']})")

    import uuid
    schedule_id = str(uuid.uuid4())
    await db.execute(
        text(
            """INSERT INTO scheduled_reconciliations
               (id, date, bank_source_id, bridge_source_id, lms_source_id,
                status, bank_ingested_at, bridge_ingested_at, lms_ingested_at, created_at)
               VALUES (:id, :date, :bank, :bridge, :lms, 'waiting_sources',
                       :bank_ts, :bridge_ts, :lms_ts, :now)"""
        ),
        {
            "id": schedule_id,
            "date": target_date,
            "bank": body.bank_source_id,
            "bridge": body.bridge_source_id,
            "lms": body.lms_source_id,
            "bank_ts": now if body.bank_source_id else None,
            "bridge_ts": now if body.bridge_source_id else None,
            "lms_ts": now if body.lms_source_id else None,
            "now": now,
        },
    )
    await db.commit()

    return {"id": schedule_id, "date": body.date, "status": "waiting_sources", "message": "Schedule created"}


@router.post("/{schedule_id}/trigger")
async def trigger_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger reconciliation for a schedule."""
    result = await db.execute(text(
        "SELECT date, status FROM scheduled_reconciliations WHERE id = :id"
    ), {"id": schedule_id})
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if row["status"] in ("running", "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"Schedule is already {row['status']}",
        )

    source_result = await db.execute(
        text(
            """
            SELECT sr.bank_source_id, sr.bridge_source_id, sr.lms_source_id,
                   b.data_date_from AS bank_data_date_from, b.data_date_to AS bank_data_date_to,
                   br.data_date_from AS bridge_data_date_from, br.data_date_to AS bridge_data_date_to,
                   l.data_date_from AS lms_data_date_from, l.data_date_to AS lms_data_date_to
            FROM scheduled_reconciliations sr
            LEFT JOIN data_sources b ON b.id = sr.bank_source_id
            LEFT JOIN data_sources br ON br.id = sr.bridge_source_id
            LEFT JOIN data_sources l ON l.id = sr.lms_source_id
            WHERE sr.id = :id
            """
        ),
        {"id": schedule_id},
    )
    source_row = source_result.mappings().first()
    if not source_row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not source_row["bank_source_id"] or not source_row["bridge_source_id"] or not source_row["lms_source_id"]:
        raise HTTPException(status_code=400, detail="Schedule is missing one or more required sources")

    schedule_date = row["date"]
    if not _covers_target_date(source_row["bank_data_date_from"], source_row["bank_data_date_to"], schedule_date):
        raise HTTPException(status_code=400, detail=f"Bank statement does not cover {schedule_date}")
    if not _covers_target_date(source_row["bridge_data_date_from"], source_row["bridge_data_date_to"], schedule_date):
        raise HTTPException(status_code=400, detail=f"Bridge file does not cover {schedule_date}")
    if not _covers_target_date(source_row["lms_data_date_from"], source_row["lms_data_date_to"], schedule_date):
        raise HTTPException(status_code=400, detail=f"LMS file does not cover {schedule_date}")

    from app.tasks.auto_reconcile import trigger_auto_reconciliation
    task = trigger_auto_reconciliation.delay(str(row["date"]))
    return {"task_id": str(task.id), "message": f"Reconciliation triggered for {row['date']}"}
