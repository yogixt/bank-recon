from celery import Celery

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
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Explicit task imports for reliable discovery
import app.tasks.parse_bank_statement  # noqa: F401,E402
import app.tasks.parse_bridge_file  # noqa: F401,E402
import app.tasks.parse_transactions  # noqa: F401,E402
import app.tasks.run_reconciliation  # noqa: F401,E402
import app.tasks.run_ai_analysis  # noqa: F401,E402
