import os
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from ..database import engine
from ..models import User, Habit, Completion, FriendRequest, Friendship

router = APIRouter(prefix="/api/debug", tags=["debug"])


def _guard():
    # Only allow if explicitly enabled
    if os.getenv("ENABLE_DEBUG_ENDPOINTS") != "1":
        raise HTTPException(status_code=404, detail="Not Found")


@router.get("/print-db")
def print_db() -> Dict[str, Any]:
    """
    Dumps entire DB contents.
    ONLY use in development.
    """
    _guard()

    with Session(engine) as s:
        users = s.exec(select(User)).all()
        habits = s.exec(select(Habit)).all()
        completions = s.exec(select(Completion)).all()
        friend_requests = s.exec(select(FriendRequest)).all()
        friendships = s.exec(select(Friendship)).all()

        return {
            "users": [u.model_dump() for u in users],
            "habits": [h.model_dump() for h in habits],
            "completions": [c.model_dump() for c in completions],
            "friend_requests": [fr.model_dump() for fr in friend_requests],
            "friendships": [fs.model_dump() for fs in friendships],
        }