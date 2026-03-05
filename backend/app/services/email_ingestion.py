"""Email ingestion orchestration: identify email -> download -> save -> create DataSource -> dispatch parse -> update schedule.

Uses AgentMail API for inbox polling and attachment downloads.
"""

import logging
import os
import re
import uuid
import zipfile
from datetime import date, datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings
from app.services.agentmail_client import list_messages, get_message, get_attachment
from app.services.time_utils import today_ist

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(get_settings().SYNC_DATABASE_URL)


def _get_existing_log(message_id: str) -> tuple[int, str] | None:
    """Return existing ingestion log id/status for a message, if present."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, status
            FROM email_ingestion_logs
            WHERE gmail_message_id = %s
            ORDER BY id DESC
            LIMIT 1""",
            (message_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row[0], row[1]
    finally:
        conn.close()


def _prepare_ingestion_log(
    message_id: str,
    email_type: str,
    sender: str,
    subject: str,
    received_at: datetime | None = None,
    attachment_filename: str | None = None,
) -> int | None:
    """Create a new log or reset failed log for retry.

    Returns a log id when processing should continue, or None when message
    should be skipped (already success/processing/skipped).
    """
    existing = _get_existing_log(message_id)
    if not existing:
        return _create_ingestion_log(
            message_id=message_id,
            email_type=email_type,
            sender=sender,
            subject=subject,
            received_at=received_at,
            attachment_filename=attachment_filename,
        )

    log_id, status = existing
    if status in ("success", "processing", "skipped"):
        return None

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE email_ingestion_logs
            SET email_type = %s,
                sender = %s,
                subject = %s,
                received_at = %s,
                attachment_filename = %s,
                data_source_id = NULL,
                status = 'processing',
                error_message = NULL,
                processed_at = NOW()
            WHERE id = %s""",
            (email_type, sender, subject, received_at, attachment_filename, log_id),
        )
        conn.commit()
        return log_id
    finally:
        conn.close()


def _create_ingestion_log(
    message_id: str,
    email_type: str,
    sender: str,
    subject: str,
    received_at: datetime | None = None,
    attachment_filename: str | None = None,
) -> int:
    """Create an email_ingestion_logs entry. Returns the log id."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO email_ingestion_logs
            (gmail_message_id, email_type, sender, subject, received_at, attachment_filename, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'processing')
            RETURNING id""",
            (message_id, email_type, sender, subject, received_at, attachment_filename),
        )
        log_id = cur.fetchone()[0]
        conn.commit()
        return log_id
    finally:
        conn.close()


def _update_ingestion_log(log_id: int, status: str, data_source_id: uuid.UUID | None = None, error_message: str | None = None):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE email_ingestion_logs SET status = %s, data_source_id = %s, error_message = %s, processed_at = NOW() WHERE id = %s",
            (status, str(data_source_id) if data_source_id else None, error_message, log_id),
        )
        conn.commit()
    finally:
        conn.close()


def _create_data_source(name: str, source_type: str, filename: str, file_path: str) -> uuid.UUID:
    """Create a data_sources entry and return its UUID."""
    ds_id = uuid.uuid4()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO data_sources (id, name, source_type, filename, file_path, status)
            VALUES (%s, %s, %s, %s, %s, 'parsing')""",
            (str(ds_id), name, source_type, filename, file_path),
        )
        conn.commit()
        return ds_id
    finally:
        conn.close()


def _get_or_create_schedule(target_date: date) -> dict:
    """Get or create a scheduled_reconciliations entry for the given date."""
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM scheduled_reconciliations WHERE date = %s", (target_date,))
        row = cur.fetchone()
        if row:
            return dict(row)
        sched_id = uuid.uuid4()
        cur.execute(
            """INSERT INTO scheduled_reconciliations (id, date, status)
            VALUES (%s, %s, 'waiting_sources')
            RETURNING *""",
            (str(sched_id), target_date),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def _update_schedule_source(target_date: date, source_field: str, source_id: uuid.UUID, ingested_field: str):
    """Update a schedule's source reference and ingested timestamp."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE scheduled_reconciliations SET {source_field} = %s, {ingested_field} = NOW() WHERE date = %s",
            (str(source_id), target_date),
        )
        conn.commit()
    finally:
        conn.close()


def _save_attachment(data: bytes, filename: str) -> str:
    """Save attachment bytes to upload dir. Returns file path."""
    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(data)
    return file_path


def _extract_from_zip(zip_path: str) -> str:
    """If file is a .zip, extract the first .xls/.xlsx inside and return its path.

    HDFC bank sends statements as password-protected .zip containing the .xls file.
    Returns the extracted file path, or the original path if not a zip.
    """
    if not zip_path.lower().endswith(".zip"):
        return zip_path

    settings = get_settings()
    pwd = settings.HDFC_ZIP_PASSWORD.encode() if settings.HDFC_ZIP_PASSWORD else None

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find the first xls/xlsx file inside
            for name in zf.namelist():
                if name.lower().endswith((".xls", ".xlsx")) and not name.startswith("__MACOSX"):
                    extract_dir = os.path.dirname(zip_path)
                    extracted = zf.extract(name, extract_dir, pwd=pwd)
                    logger.info(f"Extracted {name} from zip → {extracted}")
                    return extracted
            # If no xls found, extract the first file
            if zf.namelist():
                name = zf.namelist()[0]
                extract_dir = os.path.dirname(zip_path)
                extracted = zf.extract(name, extract_dir, pwd=pwd)
                logger.info(f"Extracted {name} from zip (no .xls found) → {extracted}")
                return extracted
    except zipfile.BadZipFile:
        logger.warning(f"Not a valid zip file: {zip_path}")
        return zip_path
    except RuntimeError as e:
        if "password" in str(e).lower():
            raise RuntimeError(f"Zip is encrypted — set HDFC_ZIP_PASSWORD in .env: {e}")
        raise
    return zip_path


def _normalize_match_text(value: str) -> str:
    """Normalize subject/pattern text for resilient matching.

    Converts separators like `_`, `-`, `:` to spaces so inputs like
    "bridge_file" match pattern "Bridge File".
    """
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _subject_matches(subject: str, pattern: str) -> bool:
    """Return True when subject contains pattern with flexible separators."""
    if not pattern:
        return False

    subject_lower = (subject or "").lower()
    pattern_lower = pattern.lower()
    if pattern_lower in subject_lower:
        return True

    normalized_subject = _normalize_match_text(subject)
    normalized_pattern = _normalize_match_text(pattern)
    return bool(normalized_pattern) and normalized_pattern in normalized_subject


def _identify_email_type(sender: str, subject: str) -> str | None:
    """Identify email type from sender/subject patterns.

    Returns: 'bank_statement', 'bridge_file', 'lms_file', or None.
    """
    settings = get_settings()
    # Bank statement: subject contains "Account Statement" (may be forwarded, so don't require sender match)
    if _subject_matches(subject, settings.HDFC_SUBJECT_PATTERN):
        return "bank_statement"

    # Bridge file: subject contains Bridge File
    if _subject_matches(subject, settings.BRIDGE_SUBJECT_PATTERN):
        return "bridge_file"

    # LMS file: subject contains LMS pattern
    if _subject_matches(subject, settings.LMS_SUBJECT_PATTERN):
        return "lms_file"

    return None


def _get_msg_attachments(msg) -> list[dict]:
    """Extract attachments from an AgentMail message object.

    Filters out inline attachments (e.g. embedded images) — only returns
    real file attachments.
    """
    attachments = []
    msg_attachments = getattr(msg, "attachments", None) or []
    for att in msg_attachments:
        att_id = getattr(att, "attachment_id", None)
        filename = getattr(att, "filename", None) or "attachment"
        content_type = getattr(att, "content_type", "") or ""
        disposition = getattr(att, "content_disposition", "") or ""

        # Skip inline attachments (embedded images etc.)
        if disposition.lower() == "inline":
            continue

        if att_id:
            attachments.append({
                "id": att_id,
                "filename": filename,
                "content_type": content_type,
            })
    return attachments


def poll_bank_statement() -> list[str]:
    """Poll AgentMail inbox for HDFC bank statement emails. Returns list of processed message IDs."""
    messages = list_messages()
    processed = []

    for msg in messages:
        msg_id = msg.message_id
        sender = getattr(msg, "from_", "") or ""
        subject = getattr(msg, "subject", "") or ""

        if _identify_email_type(sender, subject) != "bank_statement":
            continue

        log_id = _prepare_ingestion_log(
            message_id=str(msg_id),
            email_type="bank_statement",
            sender=sender,
            subject=subject,
        )
        if not log_id:
            continue

        try:
            full_msg = get_message(str(msg_id))
            attachments = _get_msg_attachments(full_msg)
            if not attachments:
                _update_ingestion_log(log_id, "skipped", error_message="No attachments found")
                continue

            att = attachments[0]
            att_data = get_attachment(str(msg_id), att["id"])
            file_path = _save_attachment(att_data, att["filename"])

            # HDFC sends bank statements as .zip — extract the .xls inside
            file_path = _extract_from_zip(file_path)

            ds_id = _create_data_source(
                name=f"Bank Statement {today_ist().isoformat()}",
                source_type="bank_statement",
                filename=os.path.basename(file_path),
                file_path=file_path,
            )

            _update_ingestion_log(log_id, "success", data_source_id=ds_id)

            # Dispatch parse task
            from app.tasks.parse_bank_statement import parse_bank_statement
            parse_bank_statement.delay(str(ds_id), file_path)

            processed.append(str(msg_id))

        except Exception as e:
            logger.exception(f"Error processing bank statement email {msg_id}")
            _update_ingestion_log(log_id, "failed", error_message=str(e))

    return processed


def poll_bridge_file() -> list[str]:
    """Poll AgentMail inbox for bridge file emails."""
    messages = list_messages()
    processed = []

    for msg in messages:
        msg_id = msg.message_id
        sender = getattr(msg, "from_", "") or ""
        subject = getattr(msg, "subject", "") or ""

        if _identify_email_type(sender, subject) != "bridge_file":
            continue

        log_id = _prepare_ingestion_log(
            message_id=str(msg_id),
            email_type="bridge_file",
            sender=sender,
            subject=subject,
        )
        if not log_id:
            continue

        try:
            full_msg = get_message(str(msg_id))
            attachments = _get_msg_attachments(full_msg)
            if not attachments:
                _update_ingestion_log(log_id, "skipped", error_message="No attachments found")
                continue

            # Guard against mislabeling LMS .xlsx as bridge files.
            bridge_atts = [
                a
                for a in attachments
                if a["filename"].lower().endswith((".txt", ".csv"))
            ]
            if not bridge_atts:
                _update_ingestion_log(log_id, "skipped", error_message="No .txt/.csv attachment found")
                continue

            att = bridge_atts[0]
            att_data = get_attachment(str(msg_id), att["id"])
            file_path = _save_attachment(att_data, att["filename"])
            ds_id = _create_data_source(
                name=f"Bridge File {today_ist().isoformat()}",
                source_type="bridge_file",
                filename=att["filename"],
                file_path=file_path,
            )

            _update_ingestion_log(log_id, "success", data_source_id=ds_id)

            from app.tasks.parse_bridge_file import parse_bridge_file
            parse_bridge_file.delay(str(ds_id), file_path)

            processed.append(str(msg_id))

        except Exception as e:
            logger.exception(f"Error processing bridge file email {msg_id}")
            _update_ingestion_log(log_id, "failed", error_message=str(e))

    return processed


def poll_lms_file() -> list[str]:
    """Poll AgentMail inbox for LMS file emails."""
    messages = list_messages()
    processed = []

    for msg in messages:
        msg_id = msg.message_id
        sender = getattr(msg, "from_", "") or ""
        subject = getattr(msg, "subject", "") or ""
        prefetched_msg = None

        identified_type = _identify_email_type(sender, subject)
        if identified_type and identified_type != "lms_file":
            continue

        # LMS: match by subject pattern OR by .xlsx attachment presence.
        # Subject-based matches win; xlsx is a fallback when no subject pattern exists.
        has_lms_subject = identified_type == "lms_file"

        # If no subject pattern match, check for .xlsx attachment
        if not has_lms_subject:
            # Peek at attachments from listing (if available)
            msg_attachments = _get_msg_attachments(msg)
            if msg_attachments:
                has_xlsx = any(a["filename"].lower().endswith(".xlsx") for a in msg_attachments)
                if not has_xlsx:
                    continue
            else:
                # Some list APIs omit attachment metadata; fetch full message to detect LMS files.
                try:
                    prefetched_msg = get_message(str(msg_id))
                except Exception as e:
                    logger.exception(f"Error checking LMS email {msg_id}: {e}")
                    continue
                full_attachments = _get_msg_attachments(prefetched_msg)
                has_xlsx = any(a["filename"].lower().endswith(".xlsx") for a in full_attachments)
                if not has_xlsx:
                    continue

        log_id = _prepare_ingestion_log(
            message_id=str(msg_id),
            email_type="lms_file",
            sender=sender,
            subject=subject,
        )
        if not log_id:
            continue

        try:
            full_msg = prefetched_msg or get_message(str(msg_id))
            attachments = _get_msg_attachments(full_msg)
            xlsx_atts = [a for a in attachments if a["filename"].lower().endswith(".xlsx")]
            if not xlsx_atts:
                _update_ingestion_log(log_id, "skipped", error_message="No .xlsx attachment found")
                continue

            att = xlsx_atts[0]
            att_data = get_attachment(str(msg_id), att["id"])
            file_path = _save_attachment(att_data, att["filename"])
            ds_id = _create_data_source(
                name=f"LMS File {today_ist().isoformat()}",
                source_type="lms_file",
                filename=att["filename"],
                file_path=file_path,
            )

            _update_ingestion_log(log_id, "success", data_source_id=ds_id)

            from app.tasks.parse_lms_file import parse_lms_file
            parse_lms_file.delay(str(ds_id), file_path)

            processed.append(str(msg_id))

        except Exception as e:
            logger.exception(f"Error processing LMS file email {msg_id}")
            _update_ingestion_log(log_id, "failed", error_message=str(e))

    return processed
