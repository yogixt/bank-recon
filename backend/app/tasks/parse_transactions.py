"""Celery task: parse transaction IDs into PostgreSQL."""

import uuid

from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.file_parser import TransactionIdParser
from app.services.bulk_db import bulk_insert_transaction_ids


@celery.task(bind=True, name="parse_transactions")
def parse_transactions(self, session_id: str, file_path: str):
    sid = uuid.UUID(session_id)
    task_id = self.request.id or str(uuid.uuid4())

    publish_progress(task_id, 10, "Parsing transaction IDs...")
    update_task_db(session_id, "parse_transactions", 10, "Parsing...", "running")

    try:
        txn_ids = TransactionIdParser.parse(file_path)
        publish_progress(task_id, 50, f"Found {len(txn_ids):,} unique IDs, inserting...")

        inserted = bulk_insert_transaction_ids(sid, txn_ids)

        publish_progress(task_id, 100, f"Done: {inserted:,} transaction IDs loaded", "completed")
        update_task_db(session_id, "parse_transactions", 100, f"Done: {inserted:,} IDs", "completed")
        return {"total_ids": inserted}

    except Exception as e:
        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(session_id, "parse_transactions", 0, str(e), "failed")
        raise
