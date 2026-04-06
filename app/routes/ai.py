from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from ..database import get_session
from ..deps import current_user
from ..models import (
    AICreateCandidateRequest,
    AIGenerateFromDraftRequest,
    AIGenerateRequest,
    AIHabitProposalRequest,
    AIIntakeRequest,
    AIPlanSnapshot,
    AIRefineCandidateRequest,
    AIRevisePlanRequest,
    AIChatRequest,
    AIChatResponse,
    Habit,
    User,
)
from ..services.ai_pipeline import (
    AIPipelineConfigError,
    AIPipelineError,
    AIPipelineGenerationError,
    create_habit_from_candidate,
    generate_habit_plan,
    generate_habit_plan_from_draft,
    propose_habit_candidates,
    process_intake_step,
    refine_habit_candidate,
    revise_habit_plan,
    chat as ai_chat,
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
    conflict_fields: List[str]
    ready_for_confirmation: bool
    confirmation_summary: Optional[str]
    needs_clarification: bool
    needs_correction: bool
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


class AIHabitCandidateResponse(BaseModel):
    title: str
    category: str
    description: str
    suggested_schedule: str
    duration_minutes: int
    rationale: str
    variant: str = "balanced"
    habit_payload: Dict[str, Any]
    progressions: List[Dict[str, Any]]


class AIHabitProposalResponse(BaseModel):
    success: bool
    provider: str
    model: str
    action: Literal["clarify", "propose", "off_topic", "sensitive", "multi_habit"]
    assistant_message: str
    what_i_heard: Optional[str]
    candidates: List[AIHabitCandidateResponse]
    needs_clarification: bool


class AIRefineCandidateResponse(BaseModel):
    success: bool
    provider: str
    model: str
    assistant_message: str
    candidate: AIHabitCandidateResponse


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
        conflict_fields=result.conflict_fields,
        ready_for_confirmation=result.ready_for_confirmation,
        confirmation_summary=result.confirmation_summary,
        needs_clarification=result.needs_clarification,
        needs_correction=result.needs_correction,
        intent=result.intent,
        realism_warning=result.realism_warning,
    )


def _candidate_response(candidate) -> AIHabitCandidateResponse:
    return AIHabitCandidateResponse(
        title=candidate.title,
        category=candidate.category,
        description=candidate.description,
        suggested_schedule=candidate.suggested_schedule,
        duration_minutes=candidate.duration_minutes,
        rationale=candidate.rationale,
        variant=candidate.variant,
        habit_payload=candidate.habit_payload.model_dump(),
        progressions=candidate.progressions,
    )


def _proposal_response(result) -> AIHabitProposalResponse:
    return AIHabitProposalResponse(
        success=True,
        provider=result.provider,
        model=result.model,
        action=result.action,
        assistant_message=result.assistant_message,
        what_i_heard=result.what_i_heard,
        candidates=[_candidate_response(candidate) for candidate in result.candidates],
        needs_clarification=result.needs_clarification,
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


@router.post("/propose-habits", response_model=AIHabitProposalResponse)
def propose_habits(
    payload: AIHabitProposalRequest,
    user: User = Depends(current_user),
):
    _ = user
    try:
        result = propose_habit_candidates(
            recent_messages=payload.recent_messages,
            latest_user_message=payload.latest_user_message,
        )
    except AIPipelineConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except AIPipelineGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except AIPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _proposal_response(result)


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


@router.post("/refine-candidate", response_model=AIRefineCandidateResponse)
def refine_candidate(
    payload: AIRefineCandidateRequest,
    user: User = Depends(current_user),
):
    _ = user
    try:
        result = refine_habit_candidate(
            idea=payload.idea,
            selected_candidate=payload.selected_candidate,
            refinement=payload.refinement,
            recent_messages=payload.recent_messages,
        )
    except AIPipelineConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except AIPipelineGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except AIPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return AIRefineCandidateResponse(
        success=True,
        provider=result.provider,
        model=result.model,
        assistant_message=result.assistant_message,
        candidate=_candidate_response(result.candidate),
    )


@router.post("/create-candidate", response_model=AICreateHabitResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: AICreateCandidateRequest,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    result = create_habit_from_candidate(payload.candidate)
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


# ---------------------------------------------------------------------------
# New unified chat endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=AIChatResponse)
def chat_endpoint(
    payload: AIChatRequest,
    user: User = Depends(current_user),
):
    """
    Single stateful chat turn. The client owns session state via `draft`.

    Actions returned:
      clarify  — assistant_message has the next question
      generate — candidates list is populated with two habit variants
      advise   — general habit-domain answer with soft pivot to creation
      redirect — out-of-scope; assistant_message explains
    """
    try:
        return ai_chat(
            message=payload.message,
            draft=payload.draft,
            recent_messages=payload.recent_messages,
        )
    except AIPipelineConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except AIPipelineGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except AIPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
