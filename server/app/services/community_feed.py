"""Create community posts from habit completions and friendship helpers."""
from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from ..models import (
    CommunityPost,
    Completion,
    Friendship,
    Habit,
    User,
)


def _friendship_pair(a: int, b: int) -> tuple[int, int]:
    low, high = sorted([a, b])
    return low, high


def are_friends(session: Session, user_a_id: int, user_b_id: int) -> bool:
    if user_a_id == user_b_id:
        return True
    low, high = _friendship_pair(user_a_id, user_b_id)
    return (
        session.exec(
            select(Friendship).where(
                Friendship.user_low_id == low, Friendship.user_high_id == high
            )
        ).first()
        is not None
    )


def friend_user_ids(session: Session, user_id: int) -> set[int]:
    """All friend user ids (not including user_id)."""
    rows = session.exec(
        select(Friendship).where(
            (Friendship.user_low_id == user_id) | (Friendship.user_high_id == user_id)
        )
    ).all()
    out: set[int] = set()
    for f in rows:
        out.add(f.user_high_id if f.user_low_id == user_id else f.user_low_id)
    return out


def compute_streak_for_habit(
    session: Session, habit_id: int, user_id: int, end_date: date
) -> int:
    """Consecutive completion days ending at end_date (inclusive)."""
    completions = session.exec(
        select(Completion).where(
            Completion.habit_id == habit_id,
            Completion.user_id == user_id,
        )
    ).all()
    dates = {c.completed_date for c in completions}
    streak = 0
    d = end_date
    while d in dates:
        streak += 1
        d -= timedelta(days=1)
    return streak


# Streak values that get a special "milestone" post type (demo-friendly).
MILESTONE_STREAKS = frozenset({3, 7, 14, 30})


def create_community_post_from_completion(
    session: Session, habit: Habit, user: User, completed_date: date
) -> None:
    """
    After a successful completion, publish one feed post for friends (and self in feed).
    Milestone streaks (3/7/14/30) use a different post_type for emphasis.
    """
    streak = compute_streak_for_habit(session, habit.id, user.id, completed_date)
    author_name = (user.name or user.email.split("@")[0]).strip() or "Someone"

    if streak in MILESTONE_STREAKS:
        post_type = "streak_milestone"
        title = f"{streak}-day streak"
        body = f"{author_name} hit a {streak}-day streak on “{habit.name}”!"
    else:
        post_type = "goal_met"
        title = "Goal completed"
        if streak > 1:
            body = f"{author_name} completed “{habit.name}” ({streak} day streak)."
        else:
            body = f"{author_name} completed “{habit.name}”."

    post = CommunityPost(
        author_id=user.id,
        habit_id=habit.id,
        post_type=post_type,
        title=title,
        body=body,
        meta_json={
            "streak": streak,
            "completed_date": completed_date.isoformat(),
            "habit_name": habit.name,
        },
    )
    session.add(post)
    session.commit()
