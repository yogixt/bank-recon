"""Publish task progress to Redis for WebSocket streaming."""

import json
import redis

from app.config import get_settings


def publish_progress(task_id: str, progress: int, message: str, status: str = "running"):
    """Publish progress update to Redis pub/sub channel."""
    settings = get_settings()
    r = redis.from_url(settings.REDIS_URL)
    payload = json.dumps({
        "task_id": task_id,
        "progress": progress,
        "message": message,
        "status": status,
    })
    r.publish(f"progress:{task_id}", payload)
    # Also store latest state for late joiners
    r.set(f"progress_state:{task_id}", payload, ex=3600)
    r.close()


def update_task_db(session_id: str, task_type: str, progress: int, message: str, status: str = "running"):
    """Update task record in database."""
    settings = get_settings()
    import psycopg2
    conn = psycopg2.connect(settings.SYNC_DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "UPDATE tasks SET progress = %s, message = %s, status = %s, "
        "updated_at = NOW() WHERE session_id = %s AND task_type = %s",
        (progress, message, status, session_id, task_type),
    )
    conn.commit()
    conn.close()
