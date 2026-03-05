"""Celery task: parse bridge file into PostgreSQL (permanent data source)."""

import uuid
from datetime import date

import psycopg2

from app.config import get_settings
from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.file_parser import BridgeFileParser
from app.services.bulk_db import bulk_insert_bridge_mappings
from app.services.date_utils import extract_date_from_transaction_id, update_date_range
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


@celery.task(bind=True, name="parse_bridge_file")
def parse_bridge_file(self, data_source_id: str, file_path: str):
    dsid = uuid.UUID(data_source_id)
    task_id = self.request.id or str(uuid.uuid4())

    publish_progress(task_id, 10, "Parsing bridge file...")
    update_task_db(data_source_id, "parse_bridge", 10, "Parsing...", "running")

    try:
        bridge_map = BridgeFileParser.parse(file_path)
        data_date_from: date | None = None
        data_date_to: date | None = None
        for txn_id in bridge_map.keys():
            parsed = extract_date_from_transaction_id(txn_id)
            data_date_from, data_date_to = update_date_range(data_date_from, data_date_to, parsed)

        publish_progress(task_id, 50, f"Found {len(bridge_map):,} mappings, inserting...")

        inserted = bulk_insert_bridge_mappings(dsid, bridge_map)

        publish_progress(task_id, 100, f"Done: {inserted:,} bridge mappings loaded", "completed")
        update_task_db(data_source_id, "parse_bridge", 100, f"Done: {inserted:,} mappings", "completed")
        _update_data_source(
            data_source_id,
            "ready",
            inserted,
            data_date_from=data_date_from,
            data_date_to=data_date_to,
        )
        _attach_to_today_schedule(
            data_source_id,
            source_field="bridge_source_id",
            ingested_field="bridge_ingested_at",
            data_date_from=data_date_from,
            data_date_to=data_date_to,
        )

        # Check if auto-reconciliation should trigger
        try:
            from app.tasks.auto_reconcile import _check_auto_reconcile
            _check_auto_reconcile()
        except Exception:
            pass

        return {"total_mappings": inserted}

    except Exception as e:
        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(data_source_id, "parse_bridge", 0, str(e), "failed")
        _update_data_source(data_source_id, "failed", 0, str(e))
        raise
