"""Unit tests for appointment_schedule helpers."""

from datetime import datetime, timezone

import pytest

from application.utils.appointment_schedule import (
    appointment_time_hhmm_valid,
    registration_schedule_valid,
    schedule_datetime_utc,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("09:30", True),
        ("00:00", True),
        ("23:59", True),
        ("9:30", False),
        ("09:5", False),
        ("24:00", False),
        ("09:60", False),
        ("", False),
        (None, False),
    ],
)
def test_appointment_time_hhmm_valid(value: str | None, expected: bool) -> None:
    assert appointment_time_hhmm_valid(value) is expected


def test_schedule_datetime_utc() -> None:
    dt = schedule_datetime_utc("2026-05-03", "14:05")
    assert dt == datetime(2026, 5, 3, 14, 5, tzinfo=timezone.utc)
    assert schedule_datetime_utc("2026-05-03", "9:30") is None
    assert schedule_datetime_utc("not-a-date", "09:30") is None


def test_registration_schedule_valid_past_date() -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    ok, msg = registration_schedule_valid("2026-05-02", "10:00", now=now)
    assert ok is False
    assert "past" in msg


def test_registration_schedule_valid_today_future_time() -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    ok, _ = registration_schedule_valid("2026-05-03", "14:00", now=now)
    assert ok is True


def test_registration_schedule_valid_today_past_time() -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    ok, msg = registration_schedule_valid("2026-05-03", "11:00", now=now)
    assert ok is False
    assert "past" in msg


def test_registration_schedule_valid_empty_date_skips() -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    ok, msg = registration_schedule_valid(None, "09:00", now=now)
    assert ok is True
    assert msg == ""
