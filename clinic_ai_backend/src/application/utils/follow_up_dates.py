"""Parse next-visit / follow-up instants for reminder scheduling."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from typing import Any


def parse_next_visit_at(value: Any) -> datetime | None:
    """
    Return timezone-aware UTC datetime for the patient's next follow-up visit, or None.

    Accepts ISO date ``YYYY-MM-DD``, ISO datetime strings, or ``datetime`` from Mongo.
    Calendar dates are interpreted as 09:00 UTC on that day (mid-morning India-friendly default).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a", "na", "tbd"}:
        return None
    # ISO datetime with optional Z
    if "T" in text or re.match(r"^\d{4}-\d{2}-\d{2} ", text):
        try:
            iso = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    # Calendar date only
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text[:10])
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return datetime.combine(d, time(9, 0, tzinfo=timezone.utc))
        except ValueError:
            return None
    return None
