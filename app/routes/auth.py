# server/app/routes/auth.py
from __future__ import annotations

import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..database import get_session
from ..models import User, UserCreate, UserLogin, UserUpdate  # UserUpdate for PATCH /me
from ..deps import current_user  # for GET /me and PATCH /me

router = APIRouter(prefix="/api/auth", tags=["auth"])

# IMPORTANT: must match deps.py, which decodes using env SECRET_KEY and HS256. :contentReference[oaicite:4]{index=4}
SECRET_KEY = os.getenv("SECRET_KEY", "changeme-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


# ----------------------------
# Password hashing (no extra deps)
# Stored format: pbkdf2_sha256$<iters>$<salt_hex>$<dk_hex>
# ----------------------------
def hash_password(password: str, iterations: int = 200_000) -> str:
    if not isinstance(password, str) or len(password) < 1:
        raise ValueError("Password required")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters_s, salt_hex, dk_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def create_access_token(sub: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    now = datetime.utcnow()
    payload: Dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
    }
    if expires_minutes and expires_minutes > 0:
        exp = now + timedelta(minutes=expires_minutes)
        payload["exp"] = int(exp.timestamp())
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def public_user(u: User) -> Dict[str, Any]:
    # Tests only need user.id, but returning a sane object is useful.
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    # Basic validation; keep it simple for tests.
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password too short")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    session.refresh(user)
    token = create_access_token(str(user.id))
    return {"user": public_user(user), "access_token": token, "token_type": "bearer"}


@router.post("/login", status_code=status.HTTP_200_OK)
def login(payload: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return {"user": public_user(user), "access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout():
    # Stateless JWT logout: tests expect 200. :contentReference[oaicite:5]{index=5}
    return {"message": "logged out"}


@router.get("/me", status_code=status.HTTP_200_OK)
def get_me(user: User = Depends(current_user)):
    return public_user(user)


@router.patch("/me", status_code=status.HTTP_200_OK)
def update_me(
    payload: UserUpdate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    if payload.name is not None:
        user.name = payload.name

    if payload.email is not None and payload.email != user.email:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = payload.email

    if payload.new_password is not None:
        if not payload.current_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="current_password required to set a new password")
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="current_password is incorrect")
        if len(payload.new_password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
        user.password_hash = hash_password(payload.new_password)

    user.updated_at = datetime.utcnow()  # set manually; onupdate is unreliable here
    session.add(user)
    session.commit()
    session.refresh(user)
    return public_user(user)