"""AgentMail SDK client for email inbox polling and sending notifications."""

import logging
from typing import Any

import httpx
from agentmail import AgentMail

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_client() -> AgentMail:
    settings = get_settings()
    if not settings.AGENTMAIL_API_KEY:
        raise RuntimeError("AGENTMAIL_API_KEY not configured")
    return AgentMail(api_key=settings.AGENTMAIL_API_KEY)


def list_messages() -> list:
    """List recent messages in the recon inbox."""
    client = _get_client()
    settings = get_settings()
    response = client.inboxes.messages.list(inbox_id=settings.AGENTMAIL_INBOX_ID)
    return getattr(response, "messages", None) or []


def get_message(message_id: str) -> Any:
    """Get full message including attachments."""
    client = _get_client()
    settings = get_settings()
    return client.inboxes.messages.get(
        inbox_id=settings.AGENTMAIL_INBOX_ID,
        message_id=message_id,
    )


def get_attachment(message_id: str, attachment_id: str) -> bytes:
    """Download attachment data.

    AgentMail's get_attachment returns an AttachmentResponse with a presigned
    download_url. We download the actual file bytes from that URL.
    """
    client = _get_client()
    settings = get_settings()
    resp = client.inboxes.messages.get_attachment(
        inbox_id=settings.AGENTMAIL_INBOX_ID,
        message_id=message_id,
        attachment_id=attachment_id,
    )
    download_url = resp.download_url
    logger.info(f"Downloading attachment {attachment_id} from {download_url[:80]}...")
    r = httpx.get(download_url, timeout=120)
    r.raise_for_status()
    return r.content


def send_email(to: str | list[str], subject: str, html_body: str, text_body: str = ""):
    """Send notification email via AgentMail."""
    client = _get_client()
    settings = get_settings()
    if isinstance(to, str):
        to = [to]
    client.inboxes.messages.send(
        inbox_id=settings.AGENTMAIL_INBOX_ID,
        to=to,
        subject=subject,
        html=html_body,
        text=text_body or subject,
    )
    logger.info(f"Email sent via AgentMail to {to}: {subject}")
