from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from ..database import get_session
from ..deps import current_user
from ..models import (
    AIGenerateFromDraftRequest,
    AIGenerateRequest,
    AIIntakeRequest,
    AIPlanSnapshot,
    AIRevisePlanRequest,
    Habit,
    User,
)
from ..services.ai_pipeline import (
    AIPipelineConfigError,
    AIPipelineError,
    AIPipelineGenerationError,
    generate_habit_plan,
    generate_habit_plan_from_draft,
    process_intake_step,
    revise_habit_plan,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AIPlanResponse(BaseModel):
    success: bool
    provider: str
    model: str
    habit_payload: Dict[str, Any]
    progressions: List[Dict[str, Any]]
    raw_plan: Dict[str, Any]


class AICreateHabitResponse(BaseModel):
    success: bool
    provider: str
    model: str
    habit: Dict[str, Any]
    habit_payload: Dict[str, Any]
    progressions: List[Dict[str, Any]]
    raw_plan: Dict[str, Any]


class AIIntakeResponse(BaseModel):
    success: bool
    assistant_message: str
    updated_draft: Dict[str, Any]
    missing_fields: List[str]
    ready_for_confirmation: bool
    confirmation_summary: Optional[str]
    needs_clarification: bool
    intent: str = "on_topic"
    realism_warning: Optional[str] = None


class AIPlanSnapshotResponse(BaseModel):
    provider: str
    model: str
    habit_payload: Dict[str, Any]
    progressions: List[Dict[str, Any]]
    raw_plan: Dict[str, Any]


class AIRevisePlanResponse(BaseModel):
    success: bool
    provider: str
    model: str
    action: Literal["plan_tweak", "reopen_intake"]
    plan_tweak: Optional[AIPlanSnapshotResponse] = None
    reopen_intake: Optional[AIIntakeResponse] = None


def _generate_or_502(payload: AIGenerateRequest):
    try:
        return generate_habit_plan(
            user_goal=payload.user_goal,
            category=payload.category,
            context=payload.context,
        )
    except AIPipelineConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except AIPipelineGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except AIPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _generate_from_draft_or_502(payload: AIGenerateFromDraftRequest):
    try:
        return generate_habit_plan_from_draft(payload.draft)
    except AIPipelineConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except AIPipelineGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except AIPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _plan_snapshot_response(result) -> AIPlanSnapshotResponse:
    return AIPlanSnapshotResponse(
        provider=result.provider,
        model=result.model,
        habit_payload=result.habit_payload.model_dump(),
        progressions=result.progressions,
        raw_plan=result.raw_plan,
    )


def _intake_response(result) -> AIIntakeResponse:
    return AIIntakeResponse(
        success=True,
        assistant_message=result.assistant_message,
        updated_draft=result.updated_draft.model_dump(),
        missing_fields=result.missing_fields,
        ready_for_confirmation=result.ready_for_confirmation,
        confirmation_summary=result.confirmation_summary,
        needs_clarification=result.needs_clarification,
        intent=result.intent,
        realism_warning=result.realism_warning,
    )


@router.post("/generate-plan", response_model=AIPlanResponse)
def generate_plan(
    payload: AIGenerateRequest,
    user: User = Depends(current_user),
):
    # `user` dependency ensures auth; the user_id comes from the token, not the client body.
    _ = user
    result = _generate_or_502(payload)
    return AIPlanResponse(
        success=True,
        provider=result.provider,
        model=result.model,
        habit_payload=result.habit_payload.model_dump(),
        progressions=result.progressions,
        raw_plan=result.raw_plan,
    )


@router.post("/intake", response_model=AIIntakeResponse)
def intake(
    payload: AIIntakeRequest,
    user: User = Depends(current_user),
):
    _ = user
    try:
        result = process_intake_step(
            recent_messages=payload.recent_messages,
            current_draft=payload.current_draft,
            latest_user_message=payload.latest_user_message,
        )
    except AIPipelineConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except AIPipelineGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except AIPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _intake_response(result)


@router.post("/generate-plan-from-draft", response_model=AIPlanResponse)
def generate_plan_from_draft(
    payload: AIGenerateFromDraftRequest,
    user: User = Depends(current_user),
):
    _ = user
    result = _generate_from_draft_or_502(payload)
    return AIPlanResponse(
        success=True,
        provider=result.provider,
        model=result.model,
        habit_payload=result.habit_payload.model_dump(),
        progressions=result.progressions,
        raw_plan=result.raw_plan,
    )


@router.post("/generate-and-create", response_model=AICreateHabitResponse, status_code=status.HTTP_201_CREATED)
def generate_and_create(
    payload: AIGenerateRequest,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    result = _generate_or_502(payload)
    db_habit = Habit(
        **result.habit_payload.model_dump(),
        user_id=user.id,
        started_at=date.today(),
    )
    session.add(db_habit)
    session.commit()
    session.refresh(db_habit)

    return AICreateHabitResponse(
        success=True,
        provider=result.provider,
        model=result.model,
        habit=db_habit.model_dump(),
        habit_payload=result.habit_payload.model_dump(),
        progressions=result.progressions,
        raw_plan=result.raw_plan,
    )


@router.post("/generate-and-create-from-draft", response_model=AICreateHabitResponse, status_code=status.HTTP_201_CREATED)
def generate_and_create_from_draft(
    payload: AIGenerateFromDraftRequest,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    result = _generate_from_draft_or_502(payload)
    db_habit = Habit(
        **result.habit_payload.model_dump(),
        user_id=user.id,
        started_at=date.today(),
    )
    session.add(db_habit)
    session.commit()
    session.refresh(db_habit)

    return AICreateHabitResponse(
        success=True,
        provider=result.provider,
        model=result.model,
        habit=db_habit.model_dump(),
        habit_payload=result.habit_payload.model_dump(),
        progressions=result.progressions,
        raw_plan=result.raw_plan,
    )


@router.post("/revise-plan", response_model=AIRevisePlanResponse)
def revise_plan(
    payload: AIRevisePlanRequest,
    user: User = Depends(current_user),
):
    _ = user
    try:
        result = revise_habit_plan(
            draft=payload.draft,
            current_plan=payload.current_plan,
            critique=payload.critique,
            recent_messages=payload.recent_messages,
        )
    except AIPipelineConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except AIPipelineGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except AIPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if result.action == "plan_tweak":
        return AIRevisePlanResponse(
            success=True,
            provider=result.provider,
            model=result.model,
            action="plan_tweak",
            plan_tweak=_plan_snapshot_response(result.plan_tweak),
        )

    return AIRevisePlanResponse(
        success=True,
        provider=result.provider,
        model=result.model,
        action="reopen_intake",
        reopen_intake=_intake_response(result.reopen_intake),
    )
