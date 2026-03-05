"""Celery tasks: auto-reconciliation trigger and full pipeline."""

import logging
import time
import uuid
from datetime import date

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings
from app.tasks.celery_app import celery
from app.services.reconciliation import run_reconciliation
from app.services.anomaly_detector import detect_anomalies
from app.services.lms_reconciliation import run_lms_verification
from app.services.bulk_db import bulk_insert_results, bulk_insert_anomalies
from app.services.notification import send_reconciliation_notification
from app.tasks.progress import update_task_db
from app.services.date_utils import extract_date_from_transaction_id
from app.services.time_utils import today_ist

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(get_settings().SYNC_DATABASE_URL)


def _covers_target_date(
    data_date_from: date | None,
    data_date_to: date | None,
    target_date: date,
) -> bool:
    if not data_date_from and not data_date_to:
        return False
    if data_date_from and data_date_from > target_date:
        return False
    if data_date_to and data_date_to < target_date:
        return False
    return True


def _check_auto_reconcile():
    """Check if all required sources are available and trigger auto-reconciliation."""
    settings = get_settings()
    if not settings.AUTO_RECONCILE_ENABLED:
        return

    today = today_ist()
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT sr.*,
                   b.data_date_from AS bank_data_date_from,
                   b.data_date_to AS bank_data_date_to,
                   br.data_date_from AS bridge_data_date_from,
                   br.data_date_to AS bridge_data_date_to,
                   l.data_date_from AS lms_data_date_from,
                   l.data_date_to AS lms_data_date_to
            FROM scheduled_reconciliations sr
            LEFT JOIN data_sources b ON b.id = sr.bank_source_id
            LEFT JOIN data_sources br ON br.id = sr.bridge_source_id
            LEFT JOIN data_sources l ON l.id = sr.lms_source_id
            WHERE sr.date = %s
            """,
            (today,),
        )
        schedule = cur.fetchone()
        if not schedule:
            return

        # Fully automated daily run needs bank + bridge + lms that cover this date.
        if (
            schedule["bank_source_id"]
            and schedule["bridge_source_id"]
            and schedule["lms_source_id"]
            and schedule["status"] == "waiting_sources"
        ):
            if not (
                _covers_target_date(schedule["bank_data_date_from"], schedule["bank_data_date_to"], today)
                and _covers_target_date(schedule["bridge_data_date_from"], schedule["bridge_data_date_to"], today)
                and _covers_target_date(schedule["lms_data_date_from"], schedule["lms_data_date_to"], today)
            ):
                logger.info(
                    "Auto-reconcile skipped for %s: one or more sources do not cover target date",
                    today.isoformat(),
                )
                return
            trigger_auto_reconciliation.delay(today.isoformat())
    finally:
        conn.close()


@celery.task(bind=True, name="trigger_auto_reconciliation")
def trigger_auto_reconciliation(self, date_str: str):
    """Full pipeline: create session -> Stage 1 -> Stage 2 -> anomaly -> notify."""
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        target_date = date.fromisoformat(date_str)

        cur.execute("SELECT * FROM scheduled_reconciliations WHERE date = %s", (target_date,))
        schedule = cur.fetchone()
        if not schedule:
            logger.error(f"No schedule found for {date_str}")
            return

        bank_source_id = schedule["bank_source_id"]
        bridge_source_id = schedule["bridge_source_id"]
        lms_source_id = schedule.get("lms_source_id")

        if not (bank_source_id and bridge_source_id and lms_source_id):
            raise ValueError("Bank statement, bridge file, and LMS file are all required")

        cur.execute(
            """
            SELECT id, source_type, status, data_date_from, data_date_to
            FROM data_sources
            WHERE id IN (%s, %s, %s)
            """,
            (str(bank_source_id), str(bridge_source_id), str(lms_source_id)),
        )
        source_rows = cur.fetchall()
        source_map = {str(r["id"]): r for r in source_rows}
        bank_row = source_map.get(str(bank_source_id))
        bridge_row = source_map.get(str(bridge_source_id))
        lms_row = source_map.get(str(lms_source_id))

        if not bank_row or bank_row["source_type"] != "bank_statement" or bank_row["status"] != "ready":
            raise ValueError("Bank statement source is missing or not ready")
        if not bridge_row or bridge_row["source_type"] != "bridge_file" or bridge_row["status"] != "ready":
            raise ValueError("Bridge file source is missing or not ready")
        if not lms_row or lms_row["source_type"] != "lms_file" or lms_row["status"] != "ready":
            raise ValueError("LMS source is missing or not ready")

        if not _covers_target_date(bank_row["data_date_from"], bank_row["data_date_to"], target_date):
            raise ValueError(f"Bank statement does not cover {target_date.isoformat()}")
        if not _covers_target_date(bridge_row["data_date_from"], bridge_row["data_date_to"], target_date):
            raise ValueError(f"Bridge file does not cover {target_date.isoformat()}")
        if not _covers_target_date(lms_row["data_date_from"], lms_row["data_date_to"], target_date):
            raise ValueError(f"LMS file does not cover {target_date.isoformat()}")

        # Mark as running
        cur.execute(
            "UPDATE scheduled_reconciliations SET status = 'running', triggered_at = NOW() WHERE id = %s",
            (str(schedule["id"]),),
        )
        conn.commit()

        # 1. Create session
        session_id = uuid.uuid4()
        cur.execute(
            """INSERT INTO reconciliation_sessions
            (id, bank_source_id, bridge_source_id, status)
            VALUES (%s, %s, %s, 'reconciling')""",
            (str(session_id), str(bank_source_id), str(bridge_source_id)),
        )
        conn.commit()

        # Link session to schedule
        cur.execute(
            "UPDATE scheduled_reconciliations SET session_id = %s WHERE id = %s",
            (str(session_id), str(schedule["id"])),
        )
        conn.commit()

        # 2. Extract transaction IDs from bridge mappings for the target date only.
        cur.execute(
            "SELECT DISTINCT transaction_id FROM bridge_mappings WHERE data_source_id = %s",
            (str(bridge_source_id),),
        )
        txn_ids = []
        for row in cur.fetchall():
            tid = row["transaction_id"]
            if extract_date_from_transaction_id(tid) == target_date:
                txn_ids.append(tid)
        if txn_ids:
            from psycopg2.extras import execute_values
            values = [(str(session_id), tid) for tid in txn_ids]
            execute_values(
                cur,
                "INSERT INTO transaction_ids (session_id, transaction_id) VALUES %s",
                values,
                page_size=1000,
            )
            conn.commit()
        else:
            raise ValueError(f"No bridge transactions found for target date {target_date.isoformat()}")

        # 3. Run Stage 1
        start = time.time()
        result = run_reconciliation(session_id)
        bulk_insert_results(session_id, result["results"])
        elapsed = time.time() - start

        # Update session stats
        stats = result["statistics"]
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
                elapsed, str(session_id),
            ),
        )
        conn.commit()

        # 4. Stage 2: LMS verification (if LMS source available)
        stage2_stats = None
        if lms_source_id:
            try:
                stage2_stats = run_lms_verification(session_id, uuid.UUID(str(lms_source_id)))
            except Exception as e:
                logger.error(f"Stage 2 LMS verification failed: {e}")

        # 5. Anomaly detection
        try:
            anomalies = detect_anomalies(session_id)
            if anomalies:
                bulk_insert_anomalies(session_id, anomalies)
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")

        # 6. Send notification
        try:
            send_reconciliation_notification(
                stage1_stats=stats,
                stage2_stats=stage2_stats,
                session_id=str(session_id),
                recon_date=date_str,
            )
        except Exception as e:
            logger.error(f"Notification failed (non-fatal): {e}")

        # 7. Update schedule
        cur.execute(
            "UPDATE scheduled_reconciliations SET status = 'completed', completed_at = NOW() WHERE id = %s",
            (str(schedule["id"]),),
        )
        conn.commit()

        logger.info(f"Auto-reconciliation complete for {date_str}: session={session_id}")
        return {
            "session_id": str(session_id),
            "stage1_stats": stats,
            "stage2_stats": stage2_stats,
        }

    except Exception as e:
        logger.exception(f"Auto-reconciliation failed for {date_str}")
        try:
            cur.execute(
                "UPDATE scheduled_reconciliations SET status = 'failed', error_message = %s WHERE date = %s",
                (str(e), date.fromisoformat(date_str)),
            )
            conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()


@celery.task(bind=True, name="run_lms_verification_task")
def run_lms_verification_task(self, session_id: str, lms_source_id: str):
    """Run Stage 2 LMS verification independently (when LMS arrives after Stage 1)."""
    try:
        update_task_db(session_id, "lms_verification", 10, "Running LMS verification...", "running")

        stats = run_lms_verification(
            uuid.UUID(session_id),
            uuid.UUID(lms_source_id),
        )

        update_task_db(
            session_id,
            "lms_verification",
            100,
            f"Done: {stats.get('total', 0):,} LMS rows verified",
            "completed",
        )

        # Send notification with Stage 2 results
        try:
            send_reconciliation_notification(
                stage1_stats={},
                stage2_stats=stats,
                session_id=session_id,
                recon_date=today_ist().isoformat(),
            )
        except Exception as e:
            logger.error(f"Stage 2 notification failed (non-fatal): {e}")

        return stats
    except Exception as e:
        update_task_db(session_id, "lms_verification", 0, str(e), "failed")
        logger.exception(f"LMS verification task failed: {e}")
        raise
