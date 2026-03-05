"""Celery task: parse bank statement Excel into PostgreSQL (permanent data source)."""

import uuid
from datetime import date

import psycopg2

from app.config import get_settings
from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.file_parser import StreamingExcelParser
from app.services.xls_parser import XlsParser, is_xls_file
from app.services.bulk_db import bulk_insert_bank_entries
from app.services.date_utils import parse_flexible_date, update_date_range
from app.services.time_utils import today_ist


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
    """Attach this source to today's schedule only when file contains today's date."""
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


@celery.task(bind=True, name="parse_bank_statement")
def parse_bank_statement(self, data_source_id: str, file_path: str):
    dsid = uuid.UUID(data_source_id)
    task_id = self.request.id or str(uuid.uuid4())

    # Auto-detect .xls (CDFV2) vs .xlsx
    if is_xls_file(file_path):
        parser = XlsParser()
    else:
        parser = StreamingExcelParser()

    publish_progress(task_id, 0, "Starting bank statement parsing...")
    # Try to update task DB if session context exists; for storage uploads this is a no-op
    update_task_db(data_source_id, "parse_bank", 0, "Starting...", "running")

    total_rows = 0
    batch_num = 0
    data_date_from: date | None = None
    data_date_to: date | None = None

    try:
        for batch in parser.parse(file_path):
            batch_num += 1
            for row in batch:
                parsed = parse_flexible_date(row.get("date"))
                data_date_from, data_date_to = update_date_range(data_date_from, data_date_to, parsed)
            inserted = bulk_insert_bank_entries(dsid, batch)
            total_rows += inserted
            progress = min(90, batch_num * 5)
            msg = f"Parsed {total_rows:,} bank entries..."
            publish_progress(task_id, progress, msg)
            update_task_db(data_source_id, "parse_bank", progress, msg)

        publish_progress(task_id, 100, f"Done: {total_rows:,} bank entries loaded", "completed")
        update_task_db(data_source_id, "parse_bank", 100, f"Done: {total_rows:,} entries", "completed")
        _update_data_source(
            data_source_id,
            "ready",
            total_rows,
            data_date_from=data_date_from,
            data_date_to=data_date_to,
        )
        _attach_to_today_schedule(
            data_source_id,
            source_field="bank_source_id",
            ingested_field="bank_ingested_at",
            data_date_from=data_date_from,
            data_date_to=data_date_to,
        )

        # Check if auto-reconciliation should trigger
        try:
            from app.tasks.auto_reconcile import _check_auto_reconcile
            _check_auto_reconcile()
        except Exception:
            pass

        return {"total_rows": total_rows}

    except Exception as e:
        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(data_source_id, "parse_bank", 0, str(e), "failed")
        _update_data_source(data_source_id, "failed", total_rows, str(e), data_date_from, data_date_to)
        raise
