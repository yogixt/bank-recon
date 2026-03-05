"""Celery task: check for stale/incomplete daily reconciliations."""

import logging

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings
from app.tasks.celery_app import celery
from app.services.notification import send_stale_alert
from app.services.time_utils import today_ist

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="check_stale_schedules")
def check_stale_schedules(self):
    """Alert if today's reconciliation is not done by the configured hour."""
    settings = get_settings()
    today = today_ist()

    conn = psycopg2.connect(settings.SYNC_DATABASE_URL)
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM scheduled_reconciliations WHERE date = %s", (today,))
        schedule = cur.fetchone()

        if not schedule:
            # No schedule exists at all - might be concerning
            missing = ["No schedule created (no files received today)"]
            try:
                send_stale_alert(today.isoformat(), missing)
            except Exception as e:
                logger.error(f"Stale alert failed: {e}")
            return {"alert": True, "missing": missing}

        if schedule["status"] == "completed":
            logger.info(f"Schedule for {today} already completed")
            return {"alert": False}

        missing = []
        if not schedule["bank_source_id"]:
            missing.append("Bank statement not received")
        if not schedule["bridge_source_id"]:
            missing.append("Bridge file not received")
        if not schedule["lms_source_id"]:
            missing.append("LMS file not received")
        if schedule["status"] == "waiting_sources":
            missing.append(f"Reconciliation not triggered (status: {schedule['status']})")
        elif schedule["status"] == "running":
            missing.append("Reconciliation still running")
        elif schedule["status"] == "failed":
            missing.append(f"Reconciliation failed: {schedule.get('error_message', 'unknown')}")

        if missing:
            try:
                send_stale_alert(today.isoformat(), missing)
            except Exception as e:
                logger.error(f"Stale alert failed: {e}")

        return {"alert": bool(missing), "missing": missing}

    finally:
        conn.close()
