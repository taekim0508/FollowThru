from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
from ..database import get_session
from ..deps import current_user
from ..models import Habit, HabitCreate, HabitUpdate, User

router = APIRouter(prefix="/api/habits", tags=["habits"])

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_habit(
    habit: HabitCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Create a new habit"""
    db_habit = Habit(**habit.model_dump(), user_id=user.id, started_at=date.today())
    session.add(db_habit)
    session.commit()
    session.refresh(db_habit)
    return db_habit

@router.get("/")
def list_habits(
    status_filter: str = "active",
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """List all user's habits"""
    query = select(Habit).where(
        Habit.user_id == user.id,
        Habit.status == status_filter
    )
    habits = session.exec(query).all()
    return habits

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

@router.put("/{habit_id}")
def update_habit(
    habit_id: int,
    habit_update: HabitUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Update a habit"""
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != user.id:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    update_data = habit_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(habit, key, value)
    
    session.add(habit)
    session.commit()
    session.refresh(habit)
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
