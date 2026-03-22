from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from ..database import get_session
from ..deps import current_user
from ..models import (
    CommentCreate,
    CommentOut,
    CommunityPost,
    FeedPostOut,
    PostComment,
    PostLike,
    User,
)
from ..services.community_feed import are_friends, friend_user_ids

router = APIRouter(prefix="/api/community", tags=["community"])


def _can_view_author(session: Session, viewer_id: int, author_id: int) -> bool:
    if viewer_id == author_id:
        return True
    return are_friends(session, viewer_id, author_id)


def _post_to_feed_out(
    session: Session, post: CommunityPost, viewer_id: int
) -> FeedPostOut:
    author = session.get(User, post.author_id)
    if not author:
        raise HTTPException(status_code=500, detail="Author missing")

    likes = session.exec(select(PostLike).where(PostLike.post_id == post.id)).all()
    like_count = len(likes)
    viewer_has_liked = any(l.user_id == viewer_id for l in likes)

    comments = session.exec(select(PostComment).where(PostComment.post_id == post.id)).all()
    comment_count = len(comments)

    return FeedPostOut(
        id=post.id,
        author_id=post.author_id,
        author_name=author.name,
        author_email=author.email,
        post_type=post.post_type,
        title=post.title,
        body=post.body,
        habit_id=post.habit_id,
        created_at=post.created_at,
        like_count=like_count,
        comment_count=comment_count,
        viewer_has_liked=viewer_has_liked,
    )


@router.get("/feed", response_model=List[FeedPostOut])
def get_feed(
    limit: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """Posts from you + your friends, newest first."""
    friends = friend_user_ids(session, user.id)
    allowed_ids = {user.id} | friends

    posts = session.exec(
        select(CommunityPost)
        .where(CommunityPost.author_id.in_(allowed_ids))
        .order_by(CommunityPost.created_at.desc())
        .limit(limit)
    ).all()

    return [_post_to_feed_out(session, p, user.id) for p in posts]


@router.post("/posts/{post_id}/like", status_code=status.HTTP_201_CREATED)
def like_post(
    post_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    post = session.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not _can_view_author(session, user.id, post.author_id):
        raise HTTPException(status_code=403, detail="Cannot view this post")

    existing = session.exec(
        select(PostLike).where(
            PostLike.post_id == post_id, PostLike.user_id == user.id
        )
    ).first()
    if existing:
        return {"message": "already liked", "liked": True}

    session.add(PostLike(post_id=post_id, user_id=user.id))
    session.commit()
    return {"message": "liked", "liked": True}


@router.delete("/posts/{post_id}/like", status_code=status.HTTP_200_OK)
def unlike_post(
    post_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    post = session.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not _can_view_author(session, user.id, post.author_id):
        raise HTTPException(status_code=403, detail="Cannot view this post")

    existing = session.exec(
        select(PostLike).where(
            PostLike.post_id == post_id, PostLike.user_id == user.id
        )
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
    return {"message": "unliked"}


@router.get("/posts/{post_id}/comments", response_model=List[CommentOut])
def list_comments(
    post_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    post = session.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not _can_view_author(session, user.id, post.author_id):
        raise HTTPException(status_code=403, detail="Cannot view this post")

    rows = session.exec(
        select(PostComment)
        .where(PostComment.post_id == post_id)
        .order_by(PostComment.created_at.asc())
    ).all()

    out: List[CommentOut] = []
    for c in rows:
        u = session.get(User, c.user_id)
        if not u:
            continue
        out.append(
            CommentOut(
                id=c.id,
                user_id=c.user_id,
                author_name=u.name,
                author_email=u.email,
                body=c.body,
                created_at=c.created_at,
            )
        )
    return out


@router.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    post_id: int,
    payload: CommentCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    post = session.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not _can_view_author(session, user.id, post.author_id):
        raise HTTPException(status_code=403, detail="Cannot view this post")

    c = PostComment(post_id=post_id, user_id=user.id, body=payload.body.strip())
    session.add(c)
    session.commit()
    session.refresh(c)
    return CommentOut(
        id=c.id,
        user_id=c.user_id,
        author_name=user.name,
        author_email=user.email,
        body=c.body,
        created_at=c.created_at,
    )
