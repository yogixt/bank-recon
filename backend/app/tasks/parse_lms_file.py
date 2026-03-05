"""Celery task: parse LMS xlsx file into PostgreSQL."""

import io
import uuid
import logging
from datetime import date

import psycopg2

from app.config import get_settings
from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.lms_parser import parse_lms_file as parse_lms
from app.services.date_utils import extract_date_from_transaction_id, parse_flexible_date, update_date_range
from app.services.time_utils import today_ist

logger = logging.getLogger(__name__)


def _update_data_source(
    data_source_id: str,
    status: str,
    row_count: int = 0,
    error_message: str | None = None,
    data_date_from: date | None = None,
    data_date_to: date | None = None,
):
    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE data_sources
            SET status = %s, row_count = %s, error_message = %s,
                data_date_from = %s, data_date_to = %s
            WHERE id = %s""",
            (status, row_count, error_message, data_date_from, data_date_to, data_source_id),
        )
        conn.commit()
    finally:
        conn.close()


def _attach_to_today_schedule(
    data_source_id: str,
    source_field: str,
    ingested_field: str,
    data_date_from: date | None,
    data_date_to: date | None,
):
    today = today_ist()
    if data_date_from is None and data_date_to is None:
        return
    if data_date_from and data_date_from > today:
        return
    if data_date_to and data_date_to < today:
        return

    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM scheduled_reconciliations WHERE date = %s", (today,))
        row = cur.fetchone()
        if not row:
            cur.execute(
                """INSERT INTO scheduled_reconciliations (id, date, status)
                VALUES (%s, %s, 'waiting_sources')
                RETURNING id""",
                (str(uuid.uuid4()), today),
            )
            row = cur.fetchone()
        schedule_id = row[0]
        cur.execute(
            f"""UPDATE scheduled_reconciliations
            SET {source_field} = %s,
                {ingested_field} = NOW(),
                status = 'waiting_sources',
                session_id = NULL,
                triggered_at = NULL,
                completed_at = NULL,
                error_message = NULL
            WHERE id = %s""",
            (data_source_id, str(schedule_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _bulk_insert_lms_entries(data_source_id: uuid.UUID, rows: list[dict]) -> int:
    """Insert LMS entries using COPY protocol."""
    if not rows:
        return 0

    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        buf = io.StringIO()
        for r in rows:
            def _clean(val):
                if val is None:
                    return "\\N"
                return str(val).replace("\t", " ").replace("\n", " ")

            created_on = r.get("created_on")
            if created_on is not None and not isinstance(created_on, str):
                created_on = str(created_on)
            last_updated = r.get("last_updated_on")
            if last_updated is not None and not isinstance(last_updated, str):
                last_updated = str(last_updated)

            line = "\t".join([
                str(data_source_id),
                _clean(r.get("user_id")),
                _clean(r.get("mobile_number")),
                _clean(r.get("role_name")),
                str(r.get("point", 0.0)),
                str(r.get("amount", 0.0)),
                _clean(created_on),
                _clean(r.get("description")),
                _clean(last_updated),
                _clean(r.get("trans_id")),
                _clean(r.get("withdraw_type")),
                _clean(r.get("state_name")),
                _clean(r.get("payment_ref_no")),
                _clean(r.get("txn_status")),
                _clean(r.get("utr_no")),
                _clean(r.get("bene_name")),
                _clean(r.get("ifsc_code")),
                _clean(r.get("credit_acc_no")),
                str(r.get("od_amount")) if r.get("od_amount") is not None else "\\N",
                _clean(r.get("reference_no")),
                _clean(r.get("txn_reference_no")),
            ])
            buf.write(line + "\n")
        buf.seek(0)

        cur = conn.cursor()
        cur.copy_from(
            buf,
            "lms_entries",
            columns=(
                "data_source_id", "user_id", "mobile_number", "role_name",
                "point", "amount", "created_on", "description",
                "last_updated_on", "trans_id", "withdraw_type", "state_name",
                "payment_ref_no", "txn_status", "utr_no", "bene_name",
                "ifsc_code", "credit_acc_no", "od_amount", "reference_no", "txn_reference_no",
            ),
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def _check_auto_reconcile_lms(lms_source_id: str):
    """If Stage 1 is already done for today, trigger Stage 2 independently."""
    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        today = today_ist()
        cur.execute(
            "SELECT session_id, status, lms_source_id FROM scheduled_reconciliations WHERE date = %s",
            (today,),
        )
        row = cur.fetchone()
        if row and row[0] and row[1] == "completed" and str(row[2]) == str(lms_source_id):
            session_id = str(row[0])
            from app.tasks.auto_reconcile import run_lms_verification_task
            run_lms_verification_task.delay(session_id, lms_source_id)
            logger.info(f"Stage 1 already done, triggered Stage 2 for session {session_id}")
    finally:
        conn.close()


@celery.task(bind=True, name="parse_lms_file")
def parse_lms_file(self, data_source_id: str, file_path: str):
    dsid = uuid.UUID(data_source_id)
    task_id = self.request.id or str(uuid.uuid4())

    publish_progress(task_id, 0, "Starting LMS file parsing...")
    update_task_db(data_source_id, "parse_lms", 0, "Starting...", "running")

    total_rows = 0
    batch_num = 0
    data_date_from: date | None = None
    data_date_to: date | None = None

    try:
        for batch in parse_lms(file_path):
            batch_num += 1
            for row in batch:
                parsed = parse_flexible_date(row.get("created_on"))
                if parsed is None:
                    parsed = extract_date_from_transaction_id(row.get("trans_id"))
                data_date_from, data_date_to = update_date_range(data_date_from, data_date_to, parsed)

            inserted = _bulk_insert_lms_entries(dsid, batch)
            total_rows += inserted
            progress = min(90, batch_num * 5)
            msg = f"Parsed {total_rows:,} LMS entries..."
            publish_progress(task_id, progress, msg)
            update_task_db(data_source_id, "parse_lms", progress, msg)

        publish_progress(task_id, 100, f"Done: {total_rows:,} LMS entries loaded", "completed")
        update_task_db(data_source_id, "parse_lms", 100, f"Done: {total_rows:,} entries", "completed")
        _update_data_source(
            data_source_id,
            "ready",
            total_rows,
            data_date_from=data_date_from,
            data_date_to=data_date_to,
        )
        _attach_to_today_schedule(
            data_source_id,
            source_field="lms_source_id",
            ingested_field="lms_ingested_at",
            data_date_from=data_date_from,
            data_date_to=data_date_to,
        )

        # Trigger full auto-reconciliation when LMS is the last required source.
        try:
            from app.tasks.auto_reconcile import _check_auto_reconcile
            _check_auto_reconcile()
        except Exception:
            pass

        # Check if Stage 2 should run independently
        _check_auto_reconcile_lms(data_source_id)

        return {"total_rows": total_rows}

    except Exception as e:
        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(data_source_id, "parse_lms", 0, str(e), "failed")
        _update_data_source(data_source_id, "failed", total_rows, str(e), data_date_from, data_date_to)
        raise
