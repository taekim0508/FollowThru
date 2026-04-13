from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field as PydanticField
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
    habits: List["Habit"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    completions: List["Completion"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    # Friend requests
    sent_friend_requests: List["FriendRequest"] = Relationship(
        back_populates="requester",
        sa_relationship_kwargs={
            "foreign_keys": "[FriendRequest.requester_id]",
            "cascade": "all, delete-orphan"
        },
    )
    received_friend_requests: List["FriendRequest"] = Relationship(
        back_populates="receiver",
        sa_relationship_kwargs={
            "foreign_keys": "[FriendRequest.receiver_id]",
            "cascade": "all, delete-orphan"
        },
    )

    # Friendships (accepted friends)
    friendships_as_low: List["Friendship"] = Relationship(
        back_populates="user_low",
        sa_relationship_kwargs={
            "foreign_keys": "[Friendship.user_low_id]",
            "cascade": "all, delete-orphan"
        },
    )
    friendships_as_high: List["Friendship"] = Relationship(
        back_populates="user_high",
        sa_relationship_kwargs={
            "foreign_keys": "[Friendship.user_high_id]",
            "cascade": "all, delete-orphan"
        },
    )

class Habit(SQLModel, table=True):
    __tablename__ = "habits"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    name: str = Field(max_length=100)
    category: str = Field(max_length=50)
    description: str

    trigger_type: str = Field(max_length=20, default="time")
    # null = no reminder set, "HH:MM" = reminder time
    trigger_value: Optional[str] = Field(default=None, max_length=10)

    frequency_type: str = Field(max_length=20)
    frequency_pattern: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))

    # NEW
    habit_type: str = Field(default="binary", max_length=20)  # binary or tracked
    target_value: Optional[float] = None

    requires_quantity: bool = Field(default=False)
    quantity_unit: Optional[str] = Field(default=None, max_length=20)
    allows_notes: bool = Field(default=True)

    motivation_statement: Optional[str] = None
    status: str = Field(default="active", max_length=20)

    # new: streak tracking

    # current_streak: number of consecutive scheduled days completed
    current_streak: int = Field(default=0)
    # max_streak: lifetime best streak — never resets
    max_streak: int = Field(default=0)
    # streak_last_updated: the completion date last counted toward streak
    # used to determine if streak is still active or broken
    streak_last_updated: Optional[date] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[date] = None
    updated_at: Optional[datetime] = Field(default=None, sa_column_kwargs={"onupdate": datetime.utcnow})

    user: Optional[User] = Relationship(back_populates="habits")
    completions: List["Completion"] = Relationship(
        back_populates="habit",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Completion(SQLModel, table=True):
    __tablename__ = "completions"

    __table_args__ = (
        UniqueConstraint("habit_id", "completed_date", name="uq_completion_habit_day"),
        Index("ix_completions_user_day", "user_id", "completed_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habits.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    completed_date: date = Field(index=True)
    completed_at: datetime = Field(default_factory=datetime.utcnow)

    # CHANGED
    progress_value: Optional[float] = None
    is_complete: bool = Field(default=False)

    note: Optional[str] = None

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


class AccountDeleteBody(BaseModel):
    """Confirm account deletion with current password."""
    password: str


class HabitCreate(BaseModel):
    name: str
    category: str
    description: str

    # trigger_type: what initiates the habit reminder ("time" = time-based, "location" = geofence-based)
    # trigger_value: the actual trigger value — for time-based habits this is "HH:MM" (e.g. "07:00")
    trigger_type: str = "time"
    # null = no reminder, "HH:MM" = reminder time (e.g. "07:00")
    trigger_value: Optional[str] = None

    # deprecated — kept for backwards compatibility with existing API callers, not used in logic
    frequency_type: str = Field(default="custom", max_length=20)

    # source of truth for scheduling — {"days": ["monday", "tuesday"...]}
    # always present, always a full list of selected days (1-7 days). all 7 days = every day.
    frequency_pattern: dict

    # "binary" = checkbox (did it or not)
    # "tracked" = numeric target (duration in minutes or count of something)
    habit_type: str = "binary"

    # numeric goal for tracked habits (e.g. 30 for "30 minutes", 10 for "10 reps")
    # null for binary habits
    target_value: Optional[float] = None

    # display label for target_value (e.g. "minutes", "pages", "reps")
    # null for binary habits
    quantity_unit: Optional[str] = None

    # deprecated — notes always allowed, kept for API compatibility
    allows_notes: bool = True

    # deprecated — redundant with habit_type=="tracked", kept for API compatibility
    requires_quantity: bool = False

    motivation_statement: Optional[str] = None


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_value: Optional[str] = None

    # deprecated — not used in logic, kept for API compatibility
    frequency_type: Optional[str] = None

    # update the scheduled days — {"days": ["monday"...]}
    frequency_pattern: Optional[dict] = None

    habit_type: Optional[str] = None
    target_value: Optional[float] = None
    quantity_unit: Optional[str] = None

    # deprecated — kept for API compatibility
    requires_quantity: Optional[bool] = None

    # allow update of motivation statement and category
    motivation_statement: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None


class CompletionCreate(SQLModel):
    completed_date: date
    progress_value: Optional[float] = None
    note: Optional[str] = None


class AIGenerateRequest(BaseModel):
    """Schema for AI habit generation request"""
    user_goal: str  # Natural language: "I want to pray except weekends"
    category: str  # fitness, study, wellness, reading, sleep
    context: Optional[dict] = None  # {"experience_level": "beginner", "available_time": 15}


class AIChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str


class AIIntakeDraft(BaseModel):
    goal_summary: Optional[str] = None
    habit_description: Optional[str] = None
    frequency: Optional[str] = None
    schedule_mode: Optional[str] = None
    times_per_week: Optional[int] = None
    schedule_text: Optional[str] = None
    schedule_days: List[str] = PydanticField(default_factory=list)
    duration_minutes: Optional[int] = None
    experience_level: Optional[str] = None
    category: Optional[str] = None
    preferred_time: str = "flexible"
    available_time: int = 15
    # Passively inferred — never explicitly asked
    motivation_statement: Optional[str] = None   # extracted from user's "why"
    habit_type: str = "binary"                   # "binary" | "tracked"
    target_value: Optional[float] = None         # for tracked habits (e.g. 5.0 for "5km")
    quantity_unit: Optional[str] = None          # for tracked habits (e.g. "km", "pages")
    trigger_value: Optional[str] = None          # "HH:MM" — extracted when user states a time


class AIIntakeRequest(BaseModel):
    recent_messages: List[AIChatMessage] = []
    current_draft: Optional[AIIntakeDraft] = None
    latest_user_message: str


class AIGenerateFromDraftRequest(BaseModel):
    draft: AIIntakeDraft


class AIPlanSnapshot(BaseModel):
    habit_payload: HabitCreate
    progressions: List[dict]


class AIRevisePlanRequest(BaseModel):
    draft: AIIntakeDraft
    current_plan: AIPlanSnapshot
    critique: str
    recent_messages: List[AIChatMessage] = []


class AIHabitCandidate(BaseModel):
    title: str
    category: str
    description: str
    suggested_schedule: str
    duration_minutes: int
    rationale: str
    variant: str = "balanced"
    habit_payload: HabitCreate
    progressions: List[dict] = PydanticField(default_factory=list)


class AIHabitProposalRequest(BaseModel):
    recent_messages: List[AIChatMessage] = []
    latest_user_message: str


class AIRefineCandidateRequest(BaseModel):
    idea: str
    selected_candidate: AIHabitCandidate
    refinement: str
    recent_messages: List[AIChatMessage] = []


class AICreateCandidateRequest(BaseModel):
    candidate: AIHabitCandidate


class AIChatRequest(BaseModel):
    """Single-turn chat request. Draft carries session state between turns."""
    message: str
    draft: AIIntakeDraft = PydanticField(default_factory=AIIntakeDraft)
    recent_messages: List[AIChatMessage] = PydanticField(default_factory=list)


class AIChatCandidate(BaseModel):
    """One habit variant returned by the chat endpoint."""
    title: str
    category: str
    description: str
    suggested_schedule: str
    duration_minutes: int
    rationale: str
    variant: str                        # "balanced" | "ambitious"
    habit_payload: HabitCreate
    progressions: List[dict] = PydanticField(default_factory=list)


class AIChatResponse(BaseModel):
    """
    action:
      clarify  — AI needs more info; assistant_message has the question
      generate — two candidates ready; candidates list is populated
      advise   — general domain advice; ends with soft habit pivot
      redirect — off-topic or out-of-scope; assistant_message explains scope
    """
    action: str
    assistant_message: str
    updated_draft: AIIntakeDraft
    candidates: List[AIChatCandidate] = PydanticField(default_factory=list)


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


# ===== COMMUNITY FEED =====


class CommunityPost(SQLModel, table=True):
    """Feed item (e.g. goal met, streak milestone). Visible to author + friends."""

    __tablename__ = "community_posts"

    id: Optional[int] = Field(default=None, primary_key=True)
    author_id: int = Field(foreign_key="users.id", index=True)
    habit_id: Optional[int] = Field(default=None, foreign_key="habits.id", index=True)

    post_type: str = Field(max_length=40)  # goal_met, streak_milestone
    title: str = Field(max_length=200)
    body: str = Field(max_length=2000)
    meta_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))

    created_at: datetime = Field(default_factory=datetime.utcnow)


class PostLike(SQLModel, table=True):
    __tablename__ = "post_likes"

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="community_posts.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_like_user"),
        Index("ix_post_likes_post", "post_id"),
    )


class PostComment(SQLModel, table=True):
    __tablename__ = "post_comments"

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="community_posts.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    body: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (Index("ix_post_comments_post", "post_id"),)


class UserSearchResult(BaseModel):
    """Search result with relationship hint for UI."""

    id: int
    email: str
    name: Optional[str] = None
    relationship: str  # none | friends | pending_sent | pending_received


class FriendProfile(BaseModel):
    id: int
    email: str
    name: Optional[str] = None


class FriendRequestInboxItem(BaseModel):
    id: int
    requester_id: int
    requester_name: Optional[str] = None
    requester_email: str
    message: Optional[str] = None
    created_at: datetime


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class FeedPostOut(BaseModel):
    id: int
    author_id: int
    author_name: Optional[str] = None
    author_email: str
    post_type: str
    title: str
    body: str
    habit_id: Optional[int] = None
    created_at: datetime
    like_count: int
    comment_count: int
    viewer_has_liked: bool


class CommentOut(BaseModel):
    id: int
    user_id: int
    author_name: Optional[str] = None
    author_email: str
    body: str
    created_at: datetime
