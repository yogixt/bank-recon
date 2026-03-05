"""Timezone helpers for daily reconciliation logic."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Return current IST datetime."""
    return datetime.now(tz=IST)


def today_ist() -> date:
    """Return current IST date for all schedule/day-bound checks."""
    return now_ist().date()

