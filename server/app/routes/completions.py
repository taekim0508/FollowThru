from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import date
from ..database import get_session
from ..deps import current_user
from ..models import Completion, CompletionCreate, Habit, User

router = APIRouter(prefix="/api/completions", tags=["completions"])

@router.post("/habits/{habit_id}/complete", status_code=status.HTTP_201_CREATED)
def complete_habit(
    habit_id: int,
    completion: CompletionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Mark a habit as completed for a specific date"""
    # Verify habit exists and belongs to user
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    # Check if already completed on this date
    existing = session.exec(
        select(Completion).where(
            Completion.habit_id == habit_id,
            Completion.completed_date == completion.completed_date
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already completed on this date")
    
    # Create completion
    db_completion = Completion(
        **completion.model_dump(),
        habit_id=habit_id,
        user_id=user.id
    )
    session.add(db_completion)
    session.commit()
    session.refresh(db_completion)
    return db_completion

@router.get("/habits/{habit_id}/completions")
def list_completions(
    habit_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """List all completions for a habit"""
    # Verify habit belongs to user
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    query = select(Completion).where(
        Completion.habit_id == habit_id
    ).order_by(Completion.completed_date.desc())
    
    completions = session.exec(query).all()
    return completions
