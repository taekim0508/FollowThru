from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from ..database import get_session
from ..deps import current_user
from ..models import Habit, HabitCreate, HabitUpdate, User, Completion
from ..services.utils import is_scheduled_day, next_scheduled_day_after

router = APIRouter(prefix="/api/habits", tags=["habits"])

VALID_CATEGORIES = {
    "Fitness",
    "Health & Wellness",
    "Work",
    "Social",
    "Lifestyle",
    "Finance",
    "Creativity",
    "Other",
}

def _check_and_reset_streaks(session: Session, user_id: int) -> None:
    """
    Evaluates all active habits for a user and resets broken streaks.
    Called once per day on app launch via POST /api/habits/check-streaks.

    Grace period rule:
    - streak doesn't break ON the next scheduled day (user still has time to complete it)
    - streak breaks the day AFTER the next scheduled day if no completion exists
    """
    today = date.today()

    habits = session.exec(
        select(Habit).where(
            Habit.user_id == user_id,
            Habit.status == "active",
        )
    ).all()

    for habit in habits:
        # nothing to reset if streak is already 0 or never started
        if habit.current_streak == 0 or habit.streak_last_updated is None:
            continue

        if not habit.frequency_pattern:
            continue

        next_expected = next_scheduled_day_after(
            habit.streak_last_updated,
            habit.frequency_pattern
        )

        if next_expected is None:
            continue

        # grace period — streak breaks the day AFTER next_expected
        # e.g. next scheduled day is Wednesday → streak safe on Wednesday
        # → breaks Thursday morning if Wednesday had no completion
        deadline = next_expected + __import__('datetime').timedelta(days=1)

        if today >= deadline:
            completion_on_expected = session.exec(
                select(Completion).where(
                    Completion.habit_id == habit.id,
                    Completion.completed_date == next_expected,
                )
            ).first()

            if not completion_on_expected:
                habit.current_streak = 0
                # max_streak is permanent — never reset
                session.add(habit)

    session.commit()


def _build_habit_response(session: Session, habit: Habit, today: date) -> dict:
    """Build the standard habit response dict — shared by list and check-streaks."""
    today_log = session.exec(
        select(Completion).where(
            Completion.habit_id == habit.id,
            Completion.completed_date == today,
        )
    ).first()

    progress = today_log.progress_value if today_log else None
    is_complete = today_log.is_complete if today_log else False

    return {
        "id": habit.id,
        "name": habit.name,
        "category": habit.category,
        "description": habit.description,
        "status": habit.status,
        "motivation_statement": habit.motivation_statement,

        # habit type and tracking
        "habit_type": habit.habit_type,
        "target_value": habit.target_value,
        "quantity_unit": habit.quantity_unit,

        # scheduling
        "trigger_type": habit.trigger_type,
        "trigger_value": habit.trigger_value,
        "frequency_pattern": habit.frequency_pattern,

        # today's progress
        "today_progress": progress,
        "today_target": habit.target_value,
        "today_complete": is_complete,

        # streak
        "current_streak": habit.current_streak,
        "max_streak": habit.max_streak,
        "streak_last_updated": habit.streak_last_updated.isoformat() if habit.streak_last_updated else None,

        # timestamps
        "created_at": habit.created_at.isoformat() if habit.created_at else None,
        "updated_at": habit.updated_at.isoformat() if habit.updated_at else None,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_habit(
        habit: HabitCreate,
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
):
    """Create a new habit."""
    if habit.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    db_habit = Habit(**habit.model_dump(), user_id=user.id, started_at=date.today())
    session.add(db_habit)
    session.commit()
    session.refresh(db_habit)
    return _build_habit_response(session, db_habit, date.today())


@router.put("/{habit_id}")
def update_habit(
        habit_id: int,
        habit_update: HabitUpdate,
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
):
    """Update a habit. habit_type cannot be changed after creation."""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    # habit_type is immutable after creation
    if habit_update.habit_type is not None and habit_update.habit_type != habit.habit_type:
        raise HTTPException(
            status_code=400,
            detail="Habit type cannot be changed after creation"
        )

    # validate category if provided
    if habit_update.category is not None and habit_update.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    update_data = habit_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(habit, key, value)

    habit.updated_at = datetime.utcnow()
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return _build_habit_response(session, habit, date.today())


@router.get("/")
def list_habits(
        status_filter: str = "active",
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
):
    """List all user's habits with today's progress and streak."""
    habits = session.exec(
        select(Habit).where(
            Habit.user_id == user.id,
            Habit.status == status_filter
        )
    ).all()

    today = date.today()
    return [_build_habit_response(session, habit, today) for habit in habits]


@router.get("/{habit_id}")
def get_habit(
        habit_id: int,
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
):
    """Get a specific habit by ID"""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit

@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(
        habit_id: int,
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
):
    """Delete a habit"""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    session.delete(habit)
    session.commit()
    return None


@router.post("/check-streaks", status_code=status.HTTP_200_OK)
def check_streaks(
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
):
    """
    Called once per day on app launch.
    Resets broken streaks, then returns updated habit list.
    iOS uses this response to refresh state — one call handles both.
    """
    _check_and_reset_streaks(session, user.id)

    today = date.today()
    habits = session.exec(
        select(Habit).where(
            Habit.user_id == user.id,
            Habit.status == "active",
        )
    ).all()

    return [_build_habit_response(session, habit, today) for habit in habits]