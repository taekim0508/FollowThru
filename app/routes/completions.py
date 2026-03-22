from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from ..database import get_session
from ..deps import current_user
from ..models import Completion, CompletionCreate, Habit, User
from ..services.community_feed import create_community_post_from_completion

router = APIRouter(prefix="/api/completions", tags=["completions"])


@router.post("/habits/{habit_id}/complete", status_code=status.HTTP_201_CREATED)
def complete_habit(
    habit_id: int,
    completion: CompletionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Mark a habit as completed/logged for a specific date"""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    existing = session.exec(
        select(Completion).where(
            Completion.habit_id == habit_id,
            Completion.completed_date == completion.completed_date,
        )
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already completed on this date")

    progress_value = completion.progress_value
    is_complete = False

    if habit.habit_type == "binary":
        is_complete = True

    elif habit.habit_type == "tracked":
        if progress_value is None:
            raise HTTPException(
                status_code=400,
                detail="Tracked habits require progress_value",
            )
        if habit.target_value is None:
            raise HTTPException(
                status_code=400,
                detail="Tracked habit missing target_value",
            )
        is_complete = progress_value >= habit.target_value

    else:
        raise HTTPException(status_code=400, detail="Invalid habit_type")

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
    session.commit()
    session.refresh(db_completion)

    if db_completion.is_complete:
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
    }


@router.get("/habits/{habit_id}/completions")
def list_completions(
    habit_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """List all completions for a habit"""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    query = select(Completion).where(
        Completion.habit_id == habit_id
    ).order_by(Completion.completed_date.desc())

    completions = session.exec(query).all()

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