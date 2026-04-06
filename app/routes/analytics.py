from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional
from calendar import monthrange

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..deps import current_user
from ..models import Completion, Habit, User
from ..services.utils import is_scheduled_day, DAY_NAMES

router = APIRouter(prefix="/api/habits", tags=["analytics"])

VALID_PERIODS = {"week", "month", "year", "all"}


# ============================================================
# DATE RANGE HELPERS
# ============================================================

def _week_range() -> tuple[date, date]:
    """Current Sun-Sat week."""
    today = date.today()
    # weekday() returns 0=Monday, 6=Sunday
    # we want Sunday as start so shift by (weekday + 1) % 7
    days_since_sunday = (today.weekday() + 1) % 7
    start = today - timedelta(days=days_since_sunday)
    end = start + timedelta(days=6)
    return start, end


def _month_range() -> tuple[date, date]:
    """First to last day of current calendar month."""
    today = date.today()
    start = date(today.year, today.month, 1)
    last_day = monthrange(today.year, today.month)[1]
    end = date(today.year, today.month, last_day)
    return start, end


def _year_range() -> tuple[date, date]:
    """Jan 1 to Dec 31 of current year."""
    today = date.today()
    start = date(today.year, 1, 1)
    end = date(today.year, 12, 31)
    return start, end


def _all_range(created_at: date) -> tuple[date, date]:
    """From habit creation date to today."""
    return created_at, date.today()


def _get_date_range(period: str, created_at: date) -> tuple[date, date]:
    if period == "week":
        return _week_range()
    elif period == "month":
        return _month_range()
    elif period == "year":
        return _year_range()
    else:
        return _all_range(created_at)


# ============================================================
# BAR GROUPING HELPERS
# ============================================================

def _all_days_in_range(start: date, end: date) -> List[date]:
    """Returns every date from start to end inclusive."""
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def _group_by_week(days: List[date]) -> List[tuple[date, date, str]]:
    """
    Groups days into Sun-Sat weeks.
    Returns list of (week_start, week_end, label) tuples.
    Label is "W1", "W2" etc.
    """
    if not days:
        return []
    groups = []
    seen_starts = set()
    week_num = 1
    for d in days:
        days_since_sunday = (d.weekday() + 1) % 7
        week_start = d - timedelta(days=days_since_sunday)
        if week_start not in seen_starts:
            seen_starts.add(week_start)
            week_end = week_start + timedelta(days=6)
            groups.append((week_start, week_end, f"W{week_num}"))
            week_num += 1
    return groups


def _group_by_month(days: List[date]) -> List[tuple[date, date, str]]:
    """
    Groups days into calendar months.
    Returns list of (month_start, month_end, label) tuples.
    Label is "Jan", "Feb" etc.
    """
    if not days:
        return []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    groups = []
    seen_months = set()
    for d in days:
        key = (d.year, d.month)
        if key not in seen_months:
            seen_months.add(key)
            month_start = date(d.year, d.month, 1)
            last_day = monthrange(d.year, d.month)[1]
            month_end = date(d.year, d.month, last_day)
            label = f"{month_names[d.month - 1]} {d.year}" if d.year != date.today().year else month_names[d.month - 1]
            groups.append((month_start, month_end, label))
    return groups


# ============================================================
# STATS HELPERS
# ============================================================

def _scheduled_days_in_range(
    start: date,
    end: date,
    frequency_pattern: dict,
    created_at: date
) -> int:
    """
    Count scheduled days in range that are on or after habit creation.
    Strict — counts all scheduled days regardless of app usage.
    """
    count = 0
    d = max(start, created_at)
    while d <= min(end, date.today()):
        if is_scheduled_day(d, frequency_pattern):
            count += 1
        d += timedelta(days=1)
    return count


def _completion_rate(completed: int, scheduled: int) -> float:
    if scheduled == 0:
        return 0.0
    return round((completed / scheduled) * 100, 1)


# ============================================================
# BAR BUILDERS
# ============================================================

def _build_binary_bars(
    period: str,
    start: date,
    end: date,
    completed_dates: set,
    frequency_pattern: dict,
    created_at: date
) -> List[dict]:
    """Build bar entries for binary habits."""
    today = date.today()
    days = _all_days_in_range(start, end)

    if period == "week":
        day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        bars = []
        for d in days:
            label = day_labels[(d.weekday() + 1) % 7]
            bars.append({
                "date": d.isoformat(),
                "label": label,
                "is_complete": d in completed_dates,
                "is_scheduled": is_scheduled_day(d, frequency_pattern) and d >= created_at and d <= today,
                "is_future": d > today,
            })
        return bars

    elif period == "month":
        bars = []
        for d in days:
            bars.append({
                "date": d.isoformat(),
                "label": str(d.day),
                "is_complete": d in completed_dates,
                "is_scheduled": is_scheduled_day(d, frequency_pattern) and d >= created_at and d <= today,
                "is_future": d > today,
            })
        return bars

    elif period == "year":
        groups = _group_by_week(days)
        bars = []
        for week_start, week_end, label in groups:
            week_days = [d for d in days if week_start <= d <= week_end]
            scheduled = [
                d for d in week_days
                if is_scheduled_day(d, frequency_pattern)
                and d >= created_at
                and d <= today
            ]
            completed = [d for d in scheduled if d in completed_dates]
            # color logic: none=grey, some=orange, all=green
            if not scheduled or all(d > today for d in week_days):
                color = "grey"
            elif len(completed) == 0:
                color = "grey"
            elif len(completed) == len(scheduled):
                color = "green"
            else:
                color = "orange"
            bars.append({
                "label": label,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "completed_count": len(completed),
                "scheduled_count": len(scheduled),
                "color": color,
                "is_future": all(d > today for d in week_days),
            })
        return bars

    else:  # all
        groups = _group_by_month(days)
        bars = []
        for month_start, month_end, label in groups:
            month_days = [d for d in days if month_start <= d <= month_end]
            scheduled = [
                d for d in month_days
                if is_scheduled_day(d, frequency_pattern)
                and d >= created_at
                and d <= today
            ]
            completed = [d for d in scheduled if d in completed_dates]
            if not scheduled:
                color = "grey"
            elif len(completed) == 0:
                color = "grey"
            elif len(completed) == len(scheduled):
                color = "green"
            else:
                color = "orange"
            bars.append({
                "label": label,
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "completed_count": len(completed),
                "scheduled_count": len(scheduled),
                "color": color,
                "is_future": all(d > today for d in month_days),
            })
        return bars


def _build_tracked_bars(
    period: str,
    start: date,
    end: date,
    completions_by_date: dict,
    frequency_pattern: dict,
    created_at: date,
    target_value: float
) -> List[dict]:
    """Build bar entries for tracked habits."""
    today = date.today()
    days = _all_days_in_range(start, end)

    if period == "week":
        day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        bars = []
        for d in days:
            label = day_labels[(d.weekday() + 1) % 7]
            completion = completions_by_date.get(d)
            value = completion.progress_value if completion else None
            is_complete = completion.is_complete if completion else False
            is_scheduled = is_scheduled_day(d, frequency_pattern) and d >= created_at and d <= today
            bars.append({
                "date": d.isoformat(),
                "label": label,
                "value": value,
                "is_complete": is_complete,
                "is_scheduled": is_scheduled,
                "is_future": d > today,
                "target_value": target_value,
            })
        return bars

    elif period == "month":
        bars = []
        for d in days:
            completion = completions_by_date.get(d)
            value = completion.progress_value if completion else None
            is_complete = completion.is_complete if completion else False
            is_scheduled = is_scheduled_day(d, frequency_pattern) and d >= created_at and d <= today
            bars.append({
                "date": d.isoformat(),
                "label": str(d.day),
                "value": value,
                "is_complete": is_complete,
                "is_scheduled": is_scheduled,
                "is_future": d > today,
                "target_value": target_value,
            })
        return bars

    elif period == "year":
        groups = _group_by_week(days)
        bars = []
        for week_start, week_end, label in groups:
            week_days = [d for d in days if week_start <= d <= week_end]
            scheduled = [
                d for d in week_days
                if is_scheduled_day(d, frequency_pattern)
                and d >= created_at
                and d <= today
            ]
            completed = [d for d in scheduled if d in completions_by_date and completions_by_date[d].is_complete]
            total_value = sum(
                completions_by_date[d].progress_value or 0
                for d in week_days
                if d in completions_by_date
            )
            if not scheduled or all(d > today for d in week_days):
                color = "grey"
            elif len(completed) == 0:
                color = "grey"
            elif len(completed) == len(scheduled):
                color = "green"
            else:
                color = "orange"
            bars.append({
                "label": label,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_value": round(total_value, 2),
                "completed_count": len(completed),
                "scheduled_count": len(scheduled),
                "color": color,
                "is_future": all(d > today for d in week_days),
            })
        return bars

    else:  # all
        groups = _group_by_month(days)
        bars = []
        for month_start, month_end, label in groups:
            month_days = [d for d in days if month_start <= d <= month_end]
            scheduled = [
                d for d in month_days
                if is_scheduled_day(d, frequency_pattern)
                and d >= created_at
                and d <= today
            ]
            completed = [d for d in scheduled if d in completions_by_date and completions_by_date[d].is_complete]
            total_value = sum(
                completions_by_date[d].progress_value or 0
                for d in month_days
                if d in completions_by_date
            )
            if not scheduled:
                color = "grey"
            elif len(completed) == 0:
                color = "grey"
            elif len(completed) == len(scheduled):
                color = "green"
            else:
                color = "orange"
            bars.append({
                "label": label,
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "total_value": round(total_value, 2),
                "completed_count": len(completed),
                "scheduled_count": len(scheduled),
                "color": color,
                "is_future": all(d > today for d in month_days),
            })
        return bars


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/{habit_id}/analytics/binary")
def get_binary_analytics(
    habit_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Analytics for binary (checkbox) habits. Returns current week (Sun-Sat)."""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")
    if habit.habit_type != "binary":
        raise HTTPException(status_code=400, detail="Use /analytics/tracked for tracked habits")

    created_at = habit.started_at or habit.created_at.date()
    start, end = _week_range()

    completions = session.exec(
        select(Completion).where(
            Completion.habit_id == habit_id,
            Completion.user_id == user.id,
        )
    ).all()

    completed_dates = {c.completed_date for c in completions}
    scheduled = _scheduled_days_in_range(start, end, habit.frequency_pattern, created_at)
    completed_in_range = sum(1 for d in completed_dates if start <= d <= end)
    completion_rate = _completion_rate(completed_in_range, scheduled)

    bars = _build_binary_bars(
        "week", start, end, completed_dates, habit.frequency_pattern, created_at
    )

    return {
        "habit_id": habit.id,
        "habit_name": habit.name,
        "habit_type": "binary",
        "period": "week",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "current_streak": habit.current_streak,
        "max_streak": habit.max_streak,
        "completion_rate": completion_rate,
        "total_completions": completed_in_range,
        "scheduled_days": scheduled,
        "bars": bars,
    }


@router.get("/{habit_id}/analytics/tracked")
def get_tracked_analytics(
    habit_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Analytics for tracked (numeric) habits. Returns current week (Sun-Sat)."""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")
    if habit.habit_type != "tracked":
        raise HTTPException(status_code=400, detail="Use /analytics/binary for binary habits")

    created_at = habit.started_at or habit.created_at.date()
    start, end = _week_range()

    completions = session.exec(
        select(Completion).where(
            Completion.habit_id == habit_id,
            Completion.user_id == user.id,
        )
    ).all()

    completions_by_date = {c.completed_date: c for c in completions}
    in_range = [c for c in completions if start <= c.completed_date <= end]
    scheduled = _scheduled_days_in_range(start, end, habit.frequency_pattern, created_at)
    completed_in_range = sum(1 for c in in_range if c.is_complete)
    completion_rate = _completion_rate(completed_in_range, scheduled)

    values_in_range = [c.progress_value for c in in_range if c.progress_value is not None]
    total_value = round(sum(values_in_range), 2) if values_in_range else None
    daily_average = round(sum(values_in_range) / len(values_in_range), 2) if values_in_range else None
    personal_best = round(max(values_in_range), 2) if values_in_range else None
    target_value = habit.target_value or 0.0

    bars = _build_tracked_bars(
        "week", start, end, completions_by_date,
        habit.frequency_pattern, created_at, target_value
    )

    return {
        "habit_id": habit.id,
        "habit_name": habit.name,
        "habit_type": "tracked",
        "quantity_unit": habit.quantity_unit,
        "target_value": habit.target_value,
        "period": "week",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "current_streak": habit.current_streak,
        "max_streak": habit.max_streak,
        "completion_rate": completion_rate,
        "total_value": total_value,
        "daily_average": daily_average,
        "personal_best": personal_best,
        "scheduled_days": scheduled,
        "completed_days": completed_in_range,
        "bars": bars,
    }