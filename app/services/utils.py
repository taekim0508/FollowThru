"""Shared utility functions used across routes and services."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


# maps Python's date.weekday() (0=Monday, 6=Sunday) to backend day name strings
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def is_scheduled_day(d: date, frequency_pattern: dict) -> bool:
    """Check if a given date falls on a scheduled day for this habit."""
    day_name = DAY_NAMES[d.weekday()]
    scheduled_days = frequency_pattern.get("days", [])
    return day_name in scheduled_days


def next_scheduled_day_after(start: date, frequency_pattern: dict) -> Optional[date]:
    """
    Find the next scheduled day strictly after start.
    Looks forward up to 7 days (one full week).
    Returns None if frequency_pattern has no scheduled days.
    """
    scheduled_days = frequency_pattern.get("days", [])
    if not scheduled_days:
        return None

    for i in range(1, 8):
        candidate = start + timedelta(days=i)
        if is_scheduled_day(candidate, frequency_pattern):
            return candidate

    return None