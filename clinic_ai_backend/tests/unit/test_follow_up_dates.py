"""Follow-up next visit date parsing."""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.application.utils.follow_up_dates import parse_next_visit_at


def test_parse_iso_date_only() -> None:
    dt = parse_next_visit_at("2030-11-05")
    assert dt is not None
    assert dt.date() == date(2030, 11, 5)
    assert dt.tzinfo == timezone.utc


def test_parse_iso_datetime_z() -> None:
    dt = parse_next_visit_at("2030-11-05T14:30:00Z")
    assert dt is not None
    assert dt.hour == 14


def test_parse_datetime_object_naive() -> None:
    dt = parse_next_visit_at(datetime(2030, 1, 2, 8, 0, 0))
    assert dt.tzinfo == timezone.utc
