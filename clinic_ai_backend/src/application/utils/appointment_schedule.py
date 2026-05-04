"""Validate appointment / registration schedule: no past dates or past times (UTC)."""

from __future__ import annotations

from datetime import datetime, time, timezone


def appointment_time_hhmm_valid(value: str | None) -> bool:
    parts = (value or "").strip().split(":")
    if len(parts) != 2:
        return False
    hour, minute = parts[0], parts[1]
    if len(hour) != 2 or len(minute) != 2 or not hour.isdigit() or not minute.isdigit():
        return False
    return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59


def schedule_datetime_utc(scheduled_date: str, scheduled_time: str) -> datetime | None:
    if not appointment_time_hhmm_valid(scheduled_time):
        return None
    try:
        d = datetime.strptime(scheduled_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    hh, mm = scheduled_time.strip().split(":")
    return datetime.combine(d, time(hour=int(hh), minute=int(mm)), tzinfo=timezone.utc)


def registration_schedule_valid(
    scheduled_date: str | None,
    scheduled_time: str | None,
    *,
    now: datetime,
) -> tuple[bool, str]:
    """
    Reject past appointment dates and (when date is today) past times. Uses UTC clock.
    Empty date skips validation (caller may fill defaults elsewhere).
    """
    sd = (scheduled_date or "").strip()
    st = (scheduled_time or "").strip()
    if not sd:
        return True, ""
    try:
        d = datetime.strptime(sd, "%Y-%m-%d").date()
    except ValueError:
        return False, "scheduled_date must be YYYY-MM-DD"
    if d < now.date():
        return False, "scheduled_date cannot be in the past"
    if not st:
        return True, ""
    if not appointment_time_hhmm_valid(st):
        return False, "scheduled_time must be HH:MM (24-hour, two digits)"
    slot = schedule_datetime_utc(sd, st)
    if slot is None:
        return False, "invalid scheduled_date or scheduled_time"
    if slot < now:
        return False, "scheduled appointment cannot be in the past"
    return True, ""
