from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from ..database import get_session
from ..deps import current_user
from ..models import Completion, CompletionCreate, Habit, User
from ..services.community_feed import create_community_post_from_completion
from ..services.utils import is_scheduled_day, next_scheduled_day_after
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/completions", tags=["completions"])


class ProgressUpdate(BaseModel):
    """Schema for updating progress on a tracked habit completion."""
    completed_date: date
    progress_value: float
    note: Optional[str] = None  # add this


def _update_streak_on_completion(habit: Habit, completed_date: date) -> None:
    """
    Updates current_streak, max_streak, streak_last_updated on the habit object.
    Called only when is_complete flips True for the first time on a given date.

    Rules:
    - first ever completion → streak = 1
    - completed_date is the next expected scheduled day → increment
    - a scheduled day was skipped → reset to 1 (fresh streak)
    - streak_last_updated == completed_date → already counted today, skip
    """
    if not habit.frequency_pattern:
        return

    # already counted today — don't double increment
    if habit.streak_last_updated == completed_date:
        return

    if habit.streak_last_updated is None:
        # first ever completion
        habit.current_streak = 1

    else:
        next_expected = next_scheduled_day_after(
            habit.streak_last_updated,
            habit.frequency_pattern
        )

        if next_expected is None:
            habit.current_streak = 1

        elif completed_date == next_expected:
            # next expected day completed — streak continues
            habit.current_streak += 1

        elif completed_date < next_expected:
            # before next expected — handle defensively
            return

        else:
            # past next expected — scheduled day was missed, reset
            habit.current_streak = 1

    # update lifetime best
    if habit.current_streak > habit.max_streak:
        habit.max_streak = habit.current_streak

    habit.streak_last_updated = completed_date


@router.post("/habits/{habit_id}/complete", status_code=status.HTTP_201_CREATED)
def complete_habit(
    habit_id: int,
    completion: CompletionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """
    Mark a habit as completed for a specific date.
    Works for both binary and tracked habits (first log of the day).
    """
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    # enforce scheduled days only
    if habit.frequency_pattern and not is_scheduled_day(
        completion.completed_date, habit.frequency_pattern
    ):
        raise HTTPException(
            status_code=400,
            detail="This habit is not scheduled for this day"
        )

    # block duplicate completions on the same date
    existing = session.exec(
        select(Completion).where(
            Completion.habit_id == habit_id,
            Completion.completed_date == completion.completed_date,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Already logged for this date — use PATCH to update progress"
        )

    # determine completion status based on habit type
    progress_value = completion.progress_value
    is_complete = False

    if habit.habit_type == "binary":
        is_complete = True

    elif habit.habit_type == "tracked":
        if progress_value is None:
            raise HTTPException(
                status_code=400,
                detail="Tracked habits require progress_value"
            )
        if habit.target_value is None:
            raise HTTPException(
                status_code=400,
                detail="Tracked habit missing target_value"
            )
        is_complete = progress_value >= habit.target_value

    else:
        raise HTTPException(status_code=400, detail="Invalid habit_type")

    # save the completion
    db_completion = Completion(
        completed_date=completion.completed_date,
        progress_value=progress_value,
        is_complete=is_complete,
        note=completion.note,
        habit_id=habit_id,
        user_id=user.id,
    )
    session.add(db_completion)
    session.flush()

    # update streak only if this counts as complete
    if is_complete:
        _update_streak_on_completion(habit, completion.completed_date)
        session.add(habit)

    session.commit()
    session.refresh(db_completion)

    # TODO: ask user if they want to post to community before creating post
    if is_complete:
        create_community_post_from_completion(
            session, habit, user, completion.completed_date
        )
        session.commit()

    return {
        "id": db_completion.id,
        "habit_id": db_completion.habit_id,
        "user_id": db_completion.user_id,
        "completed_date": db_completion.completed_date,
        "progress_value": db_completion.progress_value,
        "is_complete": db_completion.is_complete,
        "note": db_completion.note,
        "current_streak": habit.current_streak,
        "max_streak": habit.max_streak,
    }


@router.patch("/habits/{habit_id}/progress", status_code=status.HTTP_200_OK)
def update_progress(
    habit_id: int,
    payload: ProgressUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """
    Update progress on an existing tracked habit completion.
    Replaces progress_value with the new value and recalculates is_complete.
    Streak increments if is_complete flips True for the first time today.
    Streak never decrements — once counted, locked.
    Only allowed for tracked habits.
    """
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    # binary habits cannot use this endpoint
    if habit.habit_type == "binary":
        raise HTTPException(
            status_code=400,
            detail="Progress updates are only allowed for tracked habits"
        )

    if habit.target_value is None:
        raise HTTPException(
            status_code=400,
            detail="Tracked habit missing target_value"
        )

    # find existing completion for this date
    existing = session.exec(
        select(Completion).where(
            Completion.habit_id == habit_id,
            Completion.completed_date == payload.completed_date,
        )
    ).first()

    if not existing:
        raise HTTPException(
            status_code=404,
            detail="No completion found for this date — use POST to create first log"
        )

    # track whether is_complete was already True before this update
    was_complete = existing.is_complete

    # update progress and recalculate is_complete
    existing.progress_value = payload.progress_value
    existing.is_complete = payload.progress_value >= habit.target_value
    if payload.note is not None:
        existing.note = payload.note

    session.add(existing)
    session.flush()

    # increment streak only if is_complete flips True for the first time today
    # once streak is counted for this date it never decrements
    if existing.is_complete and not was_complete:
        _update_streak_on_completion(habit, payload.completed_date)
        session.add(habit)

    session.commit()
    session.refresh(existing)

    # TODO: ask user if they want to post to community before creating post
    if existing.is_complete and not was_complete:
        create_community_post_from_completion(
            session, habit, user, payload.completed_date
        )
        session.commit()

    return {
        "id": existing.id,
        "habit_id": existing.habit_id,
        "user_id": existing.user_id,
        "completed_date": existing.completed_date,
        "progress_value": existing.progress_value,
        "is_complete": existing.is_complete,
        "note": existing.note,
        "current_streak": habit.current_streak,
        "max_streak": habit.max_streak,
    }


@router.get("/habits/{habit_id}/completions")
def list_completions(
    habit_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """List all completions for a habit, newest first."""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    completions = session.exec(
        select(Completion)
        .where(Completion.habit_id == habit_id)
        .order_by(Completion.completed_date.desc())
    ).all()

    return [
        {
            "id": c.id,
            "habit_id": c.habit_id,
            "user_id": c.user_id,
            "completed_date": c.completed_date,
            "progress_value": c.progress_value,
            "is_complete": c.is_complete,
            "note": c.note,
        }
        for c in completions
    ]