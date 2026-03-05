"""Celery tasks: poll AgentMail inbox for bank statement, bridge file, and LMS file."""

import logging

from app.tasks.celery_app import celery
from app.services.email_ingestion import poll_bank_statement, poll_bridge_file, poll_lms_file

logger = logging.getLogger(__name__)


def _is_config_error(exc: Exception) -> bool:
    """Return True for AgentMail credential/configuration errors."""
    message = str(exc).lower()

    if isinstance(exc, RuntimeError) and "agentmail_api_key not configured" in message:
        return True

    if "api_key" in message and ("invalid" in message or "missing" in message or "not configured" in message):
        return True

    if "unauthorized" in message or "authentication" in message:
        return True

    return False


@celery.task(bind=True, name="poll_inbox_bank_statement")
def poll_inbox_bank_statement_task(self):
    """Poll AgentMail inbox for HDFC bank statement emails."""
    try:
        processed = poll_bank_statement()
        logger.info(f"Bank statement poll: processed {len(processed)} emails")
        return {"processed": len(processed), "message_ids": processed}
    except Exception as e:
        if _is_config_error(e):
            logger.warning("Bank statement poll skipped: %s", e)
            return {"skipped": True, "reason": str(e)}
        logger.exception(f"Bank statement poll failed: {e}")
        raise


@celery.task(bind=True, name="poll_inbox_bridge_file")
def poll_inbox_bridge_file_task(self):
    """Poll AgentMail inbox for bridge file emails."""
    try:
        processed = poll_bridge_file()
        logger.info(f"Bridge file poll: processed {len(processed)} emails")
        return {"processed": len(processed), "message_ids": processed}
    except Exception as e:
        if _is_config_error(e):
            logger.warning("Bridge file poll skipped: %s", e)
            return {"skipped": True, "reason": str(e)}
        logger.exception(f"Bridge file poll failed: {e}")
        raise


@celery.task(bind=True, name="poll_inbox_lms_file")
def poll_inbox_lms_file_task(self):
    """Poll AgentMail inbox for LMS file emails."""
    try:
        processed = poll_lms_file()
        logger.info(f"LMS file poll: processed {len(processed)} emails")
        return {"processed": len(processed), "message_ids": processed}
    except Exception as e:
        if _is_config_error(e):
            logger.warning("LMS file poll skipped: %s", e)
            return {"skipped": True, "reason": str(e)}
        logger.exception(f"LMS file poll failed: {e}")
        raise
