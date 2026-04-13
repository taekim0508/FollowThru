"""Hard-delete a user and all related rows (habits, community, friends)."""
from __future__ import annotations

from sqlalchemy import or_
from sqlmodel import Session, select

from ..models import (
    Completion,
    CommunityPost,
    FriendRequest,
    Friendship,
    Habit,
    PostComment,
    PostLike,
    User,
)


def delete_user_account_data(session: Session, user_id: int) -> None:
    """
    Remove every row referencing user_id so the account can be removed.
    Order respects foreign keys (community engagement before posts, completions before habits).
    """
    uid = user_id

    for row in session.exec(select(PostLike).where(PostLike.user_id == uid)).all():
        session.delete(row)

    for row in session.exec(select(PostComment).where(PostComment.user_id == uid)).all():
        session.delete(row)

    posts = session.exec(select(CommunityPost).where(CommunityPost.author_id == uid)).all()
    for p in posts:
        for like in session.exec(select(PostLike).where(PostLike.post_id == p.id)).all():
            session.delete(like)
        for com in session.exec(select(PostComment).where(PostComment.post_id == p.id)).all():
            session.delete(com)
        session.delete(p)

    for row in session.exec(
        select(FriendRequest).where(
            or_(
                FriendRequest.requester_id == uid,
                FriendRequest.receiver_id == uid,
            )
        )
    ).all():
        session.delete(row)

    for row in session.exec(
        select(Friendship).where(
            or_(
                Friendship.user_low_id == uid,
                Friendship.user_high_id == uid,
            )
        )
    ).all():
        session.delete(row)

    habits = session.exec(select(Habit).where(Habit.user_id == uid)).all()
    for h in habits:
        for c in session.exec(select(Completion).where(Completion.habit_id == h.id)).all():
            session.delete(c)
        session.delete(h)

    u = session.get(User, uid)
    if u is not None:
        session.delete(u)
