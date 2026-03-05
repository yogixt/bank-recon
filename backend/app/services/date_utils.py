"""Shared helpers for extracting business dates from ingested files."""

from __future__ import annotations

import re
from datetime import date, datetime

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%b %d %Y",
    "%B %d %Y",
)


def parse_flexible_date(value) -> date | None:
    """Parse mixed date values seen in XLS/XLSX/CSV ingestion rows."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    # Normalize time suffixes like "2026-03-05 00:00:00"
    text = text.replace("T", " ").split(" ", 1)[0].strip()

    # ISO-like fast path
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


def extract_date_from_transaction_id(transaction_id: str | None) -> date | None:
    """Extract YYYYMMDD date from IDs like R202603050123..."""
    if not transaction_id:
        return None
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", str(transaction_id))
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def update_date_range(current_from: date | None, current_to: date | None, candidate: date | None) -> tuple[date | None, date | None]:
    """Update min/max date range with a candidate value."""
    if candidate is None:
        return current_from, current_to

    if current_from is None or candidate < current_from:
        current_from = candidate
    if current_to is None or candidate > current_to:
        current_to = candidate
    return current_from, current_to
