from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery = Celery(
    "bank_recon",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

poll_every_seconds = max(1, int(settings.POLL_INTERVAL_MINUTES)) * 60

celery.conf.beat_schedule = {
    "poll-bank": {"task": "poll_inbox_bank_statement", "schedule": poll_every_seconds},
    "poll-bridge": {"task": "poll_inbox_bridge_file", "schedule": poll_every_seconds},
    "poll-lms": {"task": "poll_inbox_lms_file", "schedule": poll_every_seconds},
    "stale-check": {"task": "check_stale_schedules", "schedule": crontab(hour=4, minute=30)},
}

# Explicit task imports for reliable discovery
import app.tasks.parse_bank_statement  # noqa: F401,E402
import app.tasks.parse_bridge_file  # noqa: F401,E402
import app.tasks.parse_transactions  # noqa: F401,E402
import app.tasks.run_reconciliation  # noqa: F401,E402
import app.tasks.run_ai_analysis  # noqa: F401,E402
import app.tasks.poll_inbox  # noqa: F401,E402
import app.tasks.auto_reconcile  # noqa: F401,E402
import app.tasks.check_stale  # noqa: F401,E402
import app.tasks.parse_lms_file  # noqa: F401,E402
