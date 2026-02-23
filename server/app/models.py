from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, JSON, UniqueConstraint, Index

# ===== DATABASE MODELS (SQLModel - used for both DB and API responses) =====

class User(SQLModel, table=True):
    """User model - foundation for all habits and completions"""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None, sa_column_kwargs={"onupdate": datetime.utcnow})
    
    # Relationships (not stored in DB, just for querying)
    habits: List["Habit"] = Relationship(back_populates="user")
    completions: List["Completion"] = Relationship(back_populates="user")

    # Friend requests
    sent_friend_requests: List["FriendRequest"] = Relationship(
        back_populates="requester",
        sa_relationship_kwargs={"foreign_keys": "[FriendRequest.requester_id]"},
    )
    received_friend_requests: List["FriendRequest"] = Relationship(
        back_populates="receiver",
        sa_relationship_kwargs={"foreign_keys": "[FriendRequest.receiver_id]"},
    )

    # Friendships (accepted friends)
    friendships_as_low: List["Friendship"] = Relationship(
        back_populates="user_low",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_low_id]"},
    )
    friendships_as_high: List["Friendship"] = Relationship(
        back_populates="user_high",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_high_id]"},
    )

class Habit(SQLModel, table=True):
    """
    Habit model - universal schema for all habit types.
    Same columns work for fitness, study, wellness, reading, sleep.
    """
    __tablename__ = "habits"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Basic info
    name: str = Field(max_length=100)
    category: str = Field(max_length=50)  # fitness, study, wellness, reading, sleep
    description: str
    
    # Trigger info
    trigger_type: str = Field(max_length=20, default="time")
    trigger_value: str = Field(max_length=10)  # "07:00" format
    
    # Frequency info (universal via JSONB)
    frequency_type: str = Field(max_length=20)  # "daily" or "custom"
    # Use generic JSON so the skeleton works across SQLite/Postgres during early development.
    frequency_pattern: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    # Example: {"days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
    
    # Optional tracking (adapts to habit needs)
    requires_quantity: bool = Field(default=False)
    quantity_unit: Optional[str] = Field(default=None, max_length=20)  # "minutes", "pages", etc.
    allows_notes: bool = Field(default=True)
    
    # Motivation
    motivation_statement: Optional[str] = None
    
    # Status
    status: str = Field(default="active", max_length=20)  # active, paused, archived
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[date] = None
    updated_at: Optional[datetime] = Field(default=None, sa_column_kwargs={"onupdate": datetime.utcnow})
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="habits")
    completions: List["Completion"] = Relationship(back_populates="habit")


class Completion(SQLModel, table=True):
    """
    Completion model - history log of habit completions.
    One record per completed day. Critical for streak calculation.
    """
    __tablename__ = "completions"

    __table_args__ = (
        UniqueConstraint("habit_id", "completed_date", name="uq_completion_habit_day"),
        Index("ix_completions_user_day", "user_id", "completed_date"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habits.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Core data (completed_date is THE most important field)
    completed_date: date = Field(index=True)  # Used for streak calculation and calendar
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional data (per completion)
    quantity_value: Optional[float] = None  # Duration/reps if habit tracks it
    note: Optional[str] = None  # Reflection if habit allows notes
    
    # Relationships
    habit: Optional[Habit] = Relationship(back_populates="completions")
    user: Optional[User] = Relationship(back_populates="completions")


# ===== REQUEST SCHEMAS (Pydantic - only for API input validation) =====

class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for updating the authenticated user's profile"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    

class HabitCreate(BaseModel):
    """Schema for creating a new habit (from AI or manual)"""
    name: str
    category: str  # fitness, study, wellness, reading, sleep
    description: str
    trigger_type: str = "time"
    trigger_value: str  # "07:00"
    frequency_type: str  # "daily" or "custom"
    frequency_pattern: Optional[dict] = None  # {"days": ["monday", ...]}
    requires_quantity: bool = False
    quantity_unit: Optional[str] = None
    allows_notes: bool = True
    motivation_statement: Optional[str] = None


class HabitUpdate(BaseModel):
    """Schema for updating an existing habit"""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_value: Optional[str] = None
    frequency_type: Optional[str] = None
    frequency_pattern: Optional[dict] = None
    status: Optional[str] = None


class CompletionCreate(BaseModel):
    """Schema for marking a habit complete"""
    completed_date: date
    quantity_value: Optional[float] = None
    note: Optional[str] = None


class AIGenerateRequest(BaseModel):
    """Schema for AI habit generation request"""
    user_goal: str  # Natural language: "I want to pray except weekends"
    category: str  # fitness, study, wellness, reading, sleep
    context: Optional[dict] = None  # {"experience_level": "beginner", "available_time": 15}

# ===== FRIENDS MODELS =====

class FriendRequest(SQLModel, table=True):
    """
    Friend request model.
    One directional request: requester -> receiver.
    """
    __tablename__ = "friend_requests"

    id: Optional[int] = Field(default=None, primary_key=True)

    requester_id: int = Field(foreign_key="users.id", index=True)
    receiver_id: int = Field(foreign_key="users.id", index=True)

    status: str = Field(default="pending", max_length=20)
    # pending, accepted, declined, canceled

    message: Optional[str] = Field(default=None, max_length=280)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    responded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = Field(default=None, sa_column_kwargs={"onupdate": datetime.utcnow})

    # Relationships
    requester: Optional["User"] = Relationship(
        back_populates="sent_friend_requests",
        sa_relationship_kwargs={"foreign_keys": "[FriendRequest.requester_id]"},
    )
    receiver: Optional["User"] = Relationship(
        back_populates="received_friend_requests",
        sa_relationship_kwargs={"foreign_keys": "[FriendRequest.receiver_id]"},
    )

    __table_args__ = (
        # prevents duplicate pending requests in the same direction
        UniqueConstraint("requester_id", "receiver_id", name="uq_friend_request_pair"),
        Index("ix_friend_requests_receiver_status", "receiver_id", "status"),
    )


class Friendship(SQLModel, table=True):
    """
    Friendship model.
    Store accepted friendships as a single row with a canonical (user_low_id, user_high_id) ordering.
    """
    __tablename__ = "friendships"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_low_id: int = Field(foreign_key="users.id", index=True)
    user_high_id: int = Field(foreign_key="users.id", index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user_low: Optional["User"] = Relationship(
        back_populates="friendships_as_low",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_low_id]"},
    )
    user_high: Optional["User"] = Relationship(
        back_populates="friendships_as_high",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_high_id]"},
    )

    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_friendship_pair"),
        Index("ix_friendships_user_low", "user_low_id"),
        Index("ix_friendships_user_high", "user_high_id"),
    )
