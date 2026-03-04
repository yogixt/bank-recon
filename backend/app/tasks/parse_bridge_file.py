"""Celery task: parse bridge file into PostgreSQL (permanent data source)."""

import uuid

import psycopg2

from app.config import get_settings
from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.file_parser import BridgeFileParser
from app.services.bulk_db import bulk_insert_bridge_mappings


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


@celery.task(bind=True, name="parse_bridge_file")
def parse_bridge_file(self, data_source_id: str, file_path: str):
    dsid = uuid.UUID(data_source_id)
    task_id = self.request.id or str(uuid.uuid4())

    publish_progress(task_id, 10, "Parsing bridge file...")
    update_task_db(data_source_id, "parse_bridge", 10, "Parsing...", "running")

    try:
        bridge_map = BridgeFileParser.parse(file_path)
        publish_progress(task_id, 50, f"Found {len(bridge_map):,} mappings, inserting...")

        inserted = bulk_insert_bridge_mappings(dsid, bridge_map)

        publish_progress(task_id, 100, f"Done: {inserted:,} bridge mappings loaded", "completed")
        update_task_db(data_source_id, "parse_bridge", 100, f"Done: {inserted:,} mappings", "completed")
        _update_data_source(data_source_id, "ready", inserted)
        return {"total_mappings": inserted}

    except Exception as e:
        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(data_source_id, "parse_bridge", 0, str(e), "failed")
        _update_data_source(data_source_id, "failed", 0, str(e))
        raise
