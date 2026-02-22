# server/app/routes/friends.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..database import get_session
from ..deps import current_user
from ..models import User, FriendRequest, Friendship

router = APIRouter(prefix="/api/friends", tags=["friends"])


def _friendship_pair(a: int, b: int) -> tuple[int, int]:
    low, high = sorted([a, b])
    return low, high


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def send_request(
    receiver_id: int = Query(...),  # FIX: was Query(.) :contentReference[oaicite:7]{index=7}
    message: Optional[str] = Query(default=None, max_length=280),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    if receiver_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot friend yourself")

    receiver = session.get(User, receiver_id)
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")

    # Already friends?
    low, high = _friendship_pair(user.id, receiver_id)
    existing_friendship = session.exec(
        select(Friendship).where(Friendship.user_low_id == low, Friendship.user_high_id == high)
    ).first()
    if existing_friendship:
        raise HTTPException(status_code=409, detail="Already friends")

    # If a row already exists for this direction, reuse it (so you can re-request after decline/cancel)
    existing_req = session.exec(
        select(FriendRequest).where(
            FriendRequest.requester_id == user.id,
            FriendRequest.receiver_id == receiver_id,
        )
    ).first()

    if existing_req:
        if existing_req.status == "pending":
            raise HTTPException(status_code=409, detail="Request already pending")

        existing_req.status = "pending"
        existing_req.message = message
        existing_req.created_at = datetime.utcnow()
        existing_req.responded_at = None
        session.add(existing_req)
        session.commit()
        session.refresh(existing_req)
        return existing_req

    req = FriendRequest(
        requester_id=user.id,
        receiver_id=receiver_id,
        status="pending",
        message=message,
    )
    session.add(req)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Request already exists")
    session.refresh(req)
    return req


@router.get("/requests/inbox", response_model=List[FriendRequest])
def inbox(session: Session = Depends(get_session), user: User = Depends(current_user)):
    return session.exec(
        select(FriendRequest)
        .where(FriendRequest.receiver_id == user.id)
        .order_by(FriendRequest.created_at.desc())
    ).all()


@router.get("/requests/outbox", response_model=List[FriendRequest])
def outbox(session: Session = Depends(get_session), user: User = Depends(current_user)):
    return session.exec(
        select(FriendRequest)
        .where(FriendRequest.requester_id == user.id)
        .order_by(FriendRequest.created_at.desc())
    ).all()


@router.post("/requests/{request_id}/accept")
def accept_request(
    request_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    req = session.get(FriendRequest, request_id)
    if not req or req.receiver_id != user.id:
        # Tests expect 404 when requester tries to accept. :contentReference[oaicite:8]{index=8}
        raise HTTPException(status_code=404, detail="Request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")

    req.status = "accepted"
    req.responded_at = datetime.utcnow()

    low, high = _friendship_pair(req.requester_id, req.receiver_id)
    existing_friendship = session.exec(
        select(Friendship).where(Friendship.user_low_id == low, Friendship.user_high_id == high)
    ).first()
    if not existing_friendship:
        session.add(Friendship(user_low_id=low, user_high_id=high))

    session.add(req)
    session.commit()
    return {"message": "Friend request accepted"}


@router.post("/requests/{request_id}/decline")
def decline_request(
    request_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    req = session.get(FriendRequest, request_id)
    if not req or req.receiver_id != user.id:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")

    req.status = "declined"
    req.responded_at = datetime.utcnow()
    session.add(req)
    session.commit()
    return {"message": "Friend request declined"}


@router.post("/requests/{request_id}/cancel")
def cancel_request(
    request_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    req = session.get(FriendRequest, request_id)
    if not req or req.requester_id != user.id:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be canceled")

    req.status = "canceled"
    req.responded_at = datetime.utcnow()
    session.add(req)
    session.commit()
    return {"message": "Friend request canceled"}


@router.get("", response_model=List[int])
def list_friends(session: Session = Depends(get_session), user: User = Depends(current_user)):
    friendships = session.exec(
        select(Friendship).where(
            (Friendship.user_low_id == user.id) | (Friendship.user_high_id == user.id)
        )
    ).all()

    return [
        f.user_high_id if f.user_low_id == user.id else f.user_low_id
        for f in friendships
    ]


@router.delete("/{friend_id}", status_code=status.HTTP_200_OK)
def unfriend(
    friend_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    if friend_id == user.id:
        raise HTTPException(status_code=400, detail="Invalid friend id")

    low, high = _friendship_pair(user.id, friend_id)
    friendship = session.exec(
        select(Friendship).where(Friendship.user_low_id == low, Friendship.user_high_id == high)
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="Not friends")

    session.delete(friendship)
    session.commit()
    return {"message": "Unfriended"}