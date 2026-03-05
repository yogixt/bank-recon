"""Celery task: run fuzzy matching + anomaly detection after reconciliation."""

import uuid

import psycopg2

from app.config import get_settings
from app.tasks.celery_app import celery
from app.tasks.progress import publish_progress, update_task_db
from app.services.fuzzy_matcher import find_fuzzy_matches
from app.services.anomaly_detector import detect_anomalies
from app.services.bulk_db import bulk_insert_results, bulk_insert_anomalies


def _clear_anomalies(session_id: str):
    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM anomalies WHERE session_id = %s", (session_id,))
        conn.commit()
    finally:
        conn.close()


@celery.task(bind=True, name="run_ai_analysis")
def run_ai_analysis(self, session_id: str):
    sid = uuid.UUID(session_id)
    task_id = self.request.id or str(uuid.uuid4())

    publish_progress(task_id, 10, "Running fuzzy matching...")
    update_task_db(session_id, "ai_analysis", 10, "Fuzzy matching...", "running")

    try:
        # Fuzzy matching
        fuzzy_results = find_fuzzy_matches(sid)
        # Convert fuzzy matches to result rows
        fuzzy_rows = []
        for fm in fuzzy_results:
            fuzzy_rows.append({
                "transaction_id": fm["transaction_id"],
                "bank_id": fm["candidate_bank_id"],
                "date": fm.get("date"),
                "debit_amount": fm.get("debit_amount", 0.0),
                "credit_amount": fm.get("credit_amount", 0.0),
                "status": "FUZZY_MATCH",
                "description": f"Fuzzy match (similarity: {fm['similarity']}) for original bank_id: {fm['bank_id']}",
                "error_type": None,
            })
        if fuzzy_rows:
            bulk_insert_results(sid, fuzzy_rows)

        publish_progress(task_id, 50, f"Found {len(fuzzy_results)} fuzzy matches. Running anomaly detection...")
        update_task_db(session_id, "ai_analysis", 50, "Anomaly detection...", "running")

        # Anomaly detection
        _clear_anomalies(session_id)
        anomalies = detect_anomalies(sid)
        if anomalies:
            bulk_insert_anomalies(sid, anomalies)

        msg = f"Done: {len(fuzzy_results)} fuzzy matches, {len(anomalies)} anomalies detected"
        publish_progress(task_id, 100, msg, "completed")
        update_task_db(session_id, "ai_analysis", 100, msg, "completed")

        return {"fuzzy_matches": len(fuzzy_results), "anomalies": len(anomalies)}

    except Exception as e:
        publish_progress(task_id, 0, f"Error: {e}", "failed")
        update_task_db(session_id, "ai_analysis", 0, str(e), "failed")
        raise
