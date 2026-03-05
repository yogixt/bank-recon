"""Celery task: run core reconciliation after parsing is complete."""

import time
import uuid

from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.reconciliation import run_reconciliation
from app.services.bulk_db import bulk_insert_results
from app.services.time_utils import today_ist

import psycopg2
from app.config import get_settings


def _update_session_stats(session_id: str, stats: dict, processing_time: float):
    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE reconciliation_sessions SET
                status = 'completed',
                total_searched = %s, total_found = %s,
                success_count = %s, failed_count = %s,
                reversal_count = %s,
                not_in_bridge_count = %s, not_in_statement_count = %s,
                total_success_amount = %s, total_failed_amount = %s,
                total_reversal_amount = %s,
                processing_time = %s, updated_at = NOW()
            WHERE id = %s""",
            (
                stats["total_searched"], stats["total_found"],
                stats["success_count"], stats["failed_count"],
                stats["reversal_count"],
                stats["not_in_bridge"], stats["not_in_statement"],
                stats["total_success_amount"], stats["total_failed_amount"],
                stats["total_reversal_amount"],
                processing_time, session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@celery.task(bind=True, name="run_reconciliation")
def run_reconciliation_task(self, session_id: str):
    sid = uuid.UUID(session_id)
    task_id = self.request.id or str(uuid.uuid4())
    start = time.time()

    publish_progress(task_id, 5, "Loading bridge mappings...")
    update_task_db(session_id, "reconciliation", 5, "Loading data...", "running")

    try:
        publish_progress(task_id, 20, "Running reconciliation...")
        update_task_db(session_id, "reconciliation", 20, "Reconciling...", "running")

        result = run_reconciliation(sid)

        publish_progress(task_id, 70, "Saving results to database...")
        update_task_db(session_id, "reconciliation", 70, "Saving results...", "running")

        bulk_insert_results(sid, result["results"])

        elapsed = time.time() - start
        _update_session_stats(session_id, result["statistics"], elapsed)

        msg = (
            f"Done in {elapsed:.1f}s: {result['statistics']['total_found']:,} matched, "
            f"{result['statistics']['not_in_bridge']:,} not in bridge, "
            f"{result['statistics']['not_in_statement']:,} not in statement"
        )
        publish_progress(task_id, 100, msg, "completed")
        update_task_db(session_id, "reconciliation", 100, msg, "completed")

        # Send notification (non-fatal)
        try:
            from app.services.notification import send_reconciliation_notification
            send_reconciliation_notification(
                stage1_stats=result["statistics"],
                session_id=session_id,
                recon_date=today_ist().isoformat(),
            )
        except Exception:
            pass

        return result["statistics"]

    except Exception as e:
        # Mark session as failed
        conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "UPDATE reconciliation_sessions SET status = 'failed', error_message = %s WHERE id = %s",
            (str(e), session_id),
        )
        conn.commit()
        conn.close()

        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(session_id, "reconciliation", 0, str(e), "failed")
        raise
