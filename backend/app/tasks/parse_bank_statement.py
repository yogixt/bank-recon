"""Celery task: parse bank statement Excel into PostgreSQL (permanent data source)."""

import uuid

import psycopg2

from app.config import get_settings
from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.file_parser import StreamingExcelParser
from app.services.bulk_db import bulk_insert_bank_entries


def _update_data_source(data_source_id: str, status: str, row_count: int = 0, error_message: str | None = None):
    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE data_sources SET status = %s, row_count = %s, error_message = %s WHERE id = %s",
            (status, row_count, error_message, data_source_id),
        )
        conn.commit()
    finally:
        conn.close()


@celery.task(bind=True, name="parse_bank_statement")
def parse_bank_statement(self, data_source_id: str, file_path: str):
    dsid = uuid.UUID(data_source_id)
    task_id = self.request.id or str(uuid.uuid4())
    parser = StreamingExcelParser()

    publish_progress(task_id, 0, "Starting bank statement parsing...")
    # Try to update task DB if session context exists; for storage uploads this is a no-op
    update_task_db(data_source_id, "parse_bank", 0, "Starting...", "running")

    total_rows = 0
    batch_num = 0

    try:
        for batch in parser.parse(file_path):
            batch_num += 1
            inserted = bulk_insert_bank_entries(dsid, batch)
            total_rows += inserted
            progress = min(90, batch_num * 5)
            msg = f"Parsed {total_rows:,} bank entries..."
            publish_progress(task_id, progress, msg)
            update_task_db(data_source_id, "parse_bank", progress, msg)

        publish_progress(task_id, 100, f"Done: {total_rows:,} bank entries loaded", "completed")
        update_task_db(data_source_id, "parse_bank", 100, f"Done: {total_rows:,} entries", "completed")
        _update_data_source(data_source_id, "ready", total_rows)
        return {"total_rows": total_rows}

    except Exception as e:
        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(data_source_id, "parse_bank", 0, str(e), "failed")
        _update_data_source(data_source_id, "failed", total_rows, str(e))
        raise
