from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from ..config import settings
from ..models import AIChatMessage, AIIntakeDraft, AIPlanSnapshot, HabitCreate


TIME_RE = re.compile(r"^\d{2}:\d{2}$")
COUNT_PER_WEEK_RE = re.compile(r"(\d+)\s*(?:x|times?)\s*(?:a|per)?\s*week")
MINUTES_RE = re.compile(r"\b(\d+)\s*(minutes?|mins?)\b")
HOURS_RE = re.compile(r"\b(\d+)\s*(hours?|hrs?)\b")
VALID_DAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}
VALID_CATEGORIES = {"fitness", "study", "wellness", "reading", "sleep"}
VALID_EXPERIENCE_LEVELS = {"beginner", "intermediate", "advanced"}
ORDERED_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
}


class AIPipelineError(Exception):
    pass


class AIPipelineConfigError(AIPipelineError):
    pass


class AIPipelineGenerationError(AIPipelineError):
    pass


class ProgressionStep(BaseModel):
    week: int = Field(..., ge=1)
    description: str


class HabitPlanLLMOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    habit_name: str
    category: str
    description: str
    trigger_type: str = "time"
    trigger_value: str
    frequency_type: str
    frequency_pattern: Optional[dict] = None
    requires_quantity: bool = False
    quantity_unit: Optional[str] = None
    allows_notes: bool = True
    motivation_statement: Optional[str] = None
    progressions: List[ProgressionStep] = Field(default_factory=list)
    allows_photos: Optional[bool] = None


class IntakeExtractionLLMOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    goal_summary: Optional[str] = None
    habit_description: Optional[str] = None
    frequency: Optional[str] = None
    schedule_text: Optional[str] = None
    schedule_days: Optional[List[str]] = None
    duration_minutes: Optional[int] = None
    experience_level: Optional[str] = None
    category: Optional[str] = None
    category_confidence: Optional[str] = None


@dataclass
class GeneratedHabitPlan:
    habit_payload: HabitCreate
    progressions: List[Dict[str, Any]]
    raw_plan: Dict[str, Any]
    provider: str
    model: str


@dataclass
class IntakeStepResult:
    assistant_message: str
    updated_draft: AIIntakeDraft
    missing_fields: List[str]
    ready_for_confirmation: bool
    confirmation_summary: Optional[str]
    needs_clarification: bool


@dataclass
class RevisionResult:
    action: str
    provider: str
    model: str
    plan_tweak: Optional[GeneratedHabitPlan] = None
    reopen_intake: Optional[IntakeStepResult] = None


def _provider_and_model() -> tuple[str, str]:
    provider = (getattr(settings, "AI_PROVIDER", None) or os.getenv("AI_PROVIDER", "openai")).lower()
    model = getattr(settings, "OPENAI_MODEL", None) or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return provider, model


def _normalize_context(context: Optional[dict]) -> dict:
    ctx = dict(context or {})
    if not isinstance(ctx, dict):
        return {}
    return ctx


def _normalize_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.strip().split())
    return collapsed or None


def _preferred_time_default(preferred_time: str) -> str:
    pref = (preferred_time or "flexible").lower()
    if pref == "morning":
        return "07:00"
    if pref == "afternoon":
        return "14:00"
    if pref == "evening":
        return "20:00"
    return "07:00"


def _normalize_experience_level(value: Any) -> Optional[str]:
    text = (_normalize_text(value) or "").lower()
    if not text:
        return None
    if text in VALID_EXPERIENCE_LEVELS:
        return text

    beginner_markers = ["beginner", "new", "novice", "never", "first time", "just starting", "starting out"]
    intermediate_markers = ["intermediate", "some experience", "on and off", "used to", "have done this before"]
    advanced_markers = ["advanced", "experienced", "expert", "for years", "very comfortable", "already consistent"]

    if any(marker in text for marker in beginner_markers):
        return "beginner"
    if any(marker in text for marker in intermediate_markers):
        return "intermediate"
    if any(marker in text for marker in advanced_markers):
        return "advanced"
    return None


def _infer_category_from_text(text: str) -> tuple[Optional[str], bool]:
    lowered = text.lower()
    keyword_map = {
        "fitness": ["run", "running", "jog", "walk", "work out", "workout", "exercise", "gym", "lift", "yoga", "cycle"],
        "study": ["study", "learn", "practice coding", "homework", "exam", "class", "course"],
        "wellness": ["meditate", "meditation", "pray", "prayer", "journal", "journaling", "reflect", "reflection", "mindful", "wellness"],
        "reading": ["read", "reading", "book", "pages", "novel"],
        "sleep": ["sleep", "bedtime", "wind down", "wind-down", "go to bed", "night routine"],
    }
    matches = [category for category, keywords in keyword_map.items() if any(keyword in lowered for keyword in keywords)]
    if len(matches) == 1:
        return matches[0], True
    if matches:
        return matches[0], False
    return None, False


def _normalize_category(value: Any, reference_text: str = "") -> Optional[str]:
    text = (_normalize_text(value) or "").lower()
    if text in VALID_CATEGORIES:
        return text
    inferred, confident = _infer_category_from_text(" ".join(filter(None, [text, reference_text])))
    return inferred if confident else None


def _canonical_frequency(value: Any) -> Optional[str]:
    text = (_normalize_text(value) or "").lower()
    if not text:
        return None

    if any(phrase in text for phrase in ["every day", "daily", "each day"]):
        return "every day"
    if any(phrase in text for phrase in ["weekday", "weekdays", "monday to friday", "mon-fri", "except weekends"]):
        return "weekdays"
    if "weekend" in text:
        return "weekends"

    match = COUNT_PER_WEEK_RE.search(text)
    if match:
        return f"{match.group(1)} times per week"

    explicit_days = [day for day in ORDERED_DAYS if day in text]
    if explicit_days:
        ordered = [day for day in ORDERED_DAYS if day in explicit_days]
        return ", ".join(ordered)

    if any(phrase in text for phrase in ["once a week", "twice a week", "every other day", "every morning", "every evening"]):
        return _normalize_text(value)

    return None


def _frequency_from_text(text: str) -> tuple[str, Optional[dict]]:
    lowered = text.lower()
    if "every day" in lowered or "daily" in lowered or "each day" in lowered:
        return "daily", None
    if any(phrase in lowered for phrase in ["weekday", "weekdays", "monday to friday", "mon-fri", "except weekends"]):
        return "custom", {"days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
    if "weekend" in lowered:
        return "custom", {"days": ["saturday", "sunday"]}

    explicit_days = [day for day in ORDERED_DAYS if day in lowered]
    if explicit_days:
        return "custom", {"days": explicit_days}

    match = COUNT_PER_WEEK_RE.search(lowered)
    if match:
        count = max(1, min(int(match.group(1)), 7))
        day_sets = {
            1: ["monday"],
            2: ["monday", "thursday"],
            3: ["monday", "wednesday", "friday"],
            4: ["monday", "tuesday", "thursday", "friday"],
            5: ["monday", "tuesday", "wednesday", "thursday", "friday"],
            6: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
            7: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        }
        days = day_sets[count]
        return ("daily", None) if len(days) == 7 else ("custom", {"days": days})

    return "daily", None


def _clean_schedule_days(days: Any) -> List[str]:
    if not isinstance(days, list):
        return []
    cleaned: List[str] = []
    for day in days:
        if not isinstance(day, str):
            continue
        normalized = day.strip().lower()
        if normalized in VALID_DAYS and normalized not in cleaned:
            cleaned.append(normalized)
    return [day for day in ORDERED_DAYS if day in cleaned]


def _schedule_days_from_text(value: Any) -> List[str]:
    text = (_normalize_text(value) or "").lower()
    if not text:
        return []
    if any(phrase in text for phrase in ["every day", "daily", "each day"]):
        return ORDERED_DAYS.copy()
    if any(phrase in text for phrase in ["weekday", "weekdays", "monday to friday", "mon-fri", "except weekends"]):
        return ORDERED_DAYS[:5]
    if "weekend" in text:
        return ORDERED_DAYS[5:]
    return [day for day in ORDERED_DAYS if day in text]


def _schedule_text_from_value(value: Any) -> Optional[str]:
    frequency = _canonical_frequency(value)
    if not frequency:
        return None
    if COUNT_PER_WEEK_RE.search(frequency):
        return None
    if frequency == "every day":
        return "every day"
    days = _schedule_days_from_text(frequency)
    if not days:
        return None
    return ", ".join(days) if days != ORDERED_DAYS else "every day"


def _schedule_text_from_days(days: List[str]) -> Optional[str]:
    if not days:
        return None
    if days == ORDERED_DAYS:
        return "every day"
    return ", ".join(days)


def _number_from_words(text: str) -> Optional[int]:
    cleaned = text.replace("-", " ").strip().lower()
    if not cleaned:
        return None
    if cleaned in {"a", "an"}:
        return 1
    tokens = [token for token in cleaned.split() if token in NUMBER_WORDS]
    if not tokens:
        return None
    if len(tokens) == 1:
        return NUMBER_WORDS[tokens[0]]
    if len(tokens) == 2 and NUMBER_WORDS[tokens[0]] >= 20 and NUMBER_WORDS[tokens[1]] < 10:
        return NUMBER_WORDS[tokens[0]] + NUMBER_WORDS[tokens[1]]
    return None


def _duration_minutes_from_text(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return max(1, min(value, 240))
    text = (_normalize_text(value) or "").lower()
    if not text:
        return None
    if "half an hour" in text or "half hour" in text:
        return 30

    minute_match = MINUTES_RE.search(text)
    if minute_match:
        return max(1, min(int(minute_match.group(1)), 240))

    hour_match = HOURS_RE.search(text)
    if hour_match:
        return max(1, min(int(hour_match.group(1)) * 60, 240))

    word_minute_match = re.search(r"\b([a-z][a-z\s-]*)\s*(minutes?|mins?)\b", text)
    if word_minute_match:
        number = _number_from_words(word_minute_match.group(1))
        if number is not None:
            return max(1, min(number, 240))

    word_hour_match = re.search(r"\b([a-z][a-z\s-]*)\s*(hours?|hrs?)\b", text)
    if word_hour_match:
        number = _number_from_words(word_hour_match.group(1))
        if number is not None:
            return max(1, min(number * 60, 240))

    return None


def _build_prompt(user_goal: str, category: str, context: Optional[dict]) -> str:
    ctx = _normalize_context(context)
    exp = ctx.get("experience_level", "beginner")
    available_time = ctx.get("available_time", 15)
    preferred_time = ctx.get("preferred_time", "flexible")
    habit_description = ctx.get("habit_description")
    frequency = ctx.get("frequency")
    schedule_text = ctx.get("schedule_text")
    schedule_days = ctx.get("schedule_days")
    duration_minutes = ctx.get("duration_minutes")
    critique = ctx.get("critique")
    current_plan = ctx.get("current_plan")

    extra_sections = []
    if habit_description:
        extra_sections.append(f'Habit Description: "{habit_description}"')
    if frequency:
        extra_sections.append(f'Desired Frequency: "{frequency}"')
    if schedule_text:
        extra_sections.append(f'Desired Schedule: "{schedule_text}"')
    if schedule_days:
        extra_sections.append(f"Desired Schedule Days: {json.dumps(schedule_days)}")
    if duration_minutes:
        extra_sections.append(f"Desired Duration (minutes): {duration_minutes}")
    if critique:
        extra_sections.append(f'Revision Critique: "{critique}"')
    if current_plan:
        extra_sections.append(f"Current Plan Snapshot: {json.dumps(current_plan)}")

    extra_block = "\n".join(extra_sections)
    if extra_block:
        extra_block = f"{extra_block}\n"

    return f"""
You are a habit formation coach. Generate a practical starter habit plan.

User Goal: "{user_goal}"
Category: {category}
{extra_block}Experience Level: {exp}
Available Time (minutes): {available_time}
Preferred Time: {preferred_time}

Return ONLY valid JSON (no markdown, no prose) with this shape:
{{
  "habit_name": "string",
  "category": "{category}",
  "description": "string",
  "trigger_type": "time",
  "trigger_value": "HH:MM",
  "frequency_type": "daily" or "custom",
  "frequency_pattern": null or {{"days": ["monday","tuesday"]}},
  "requires_quantity": false,
  "quantity_unit": null,
  "allows_notes": true,
  "motivation_statement": "string",
  "progressions": [
    {{"week": 2, "description": "string"}},
    {{"week": 4, "description": "string"}}
  ]
}}

Rules:
- Start small for the user's experience level.
- Respect available time.
- The desired frequency, if provided, takes priority over inferring cadence from the goal.
- Respect the desired schedule and duration if they are provided.
- Progressions should stay advisory and realistic.
- If preferred_time is morning/afternoon/evening, choose an appropriate time.
- trigger_type must be "time".
""".strip()


def _title_for_category(category: str) -> str:
    return {
        "wellness": "Daily Reflection",
        "fitness": "Steady Movement",
        "study": "Focused Study Block",
        "reading": "Reading Sprint",
        "sleep": "Sleep Wind-Down",
    }.get(category, "New Habit")


def _description_for_category(category: str, habit_description: Optional[str]) -> str:
    if habit_description:
        return habit_description
    return {
        "wellness": "Spend a few minutes in reflection or prayer",
        "fitness": "Move your body in a manageable way",
        "study": "Do one focused block of study",
        "reading": "Read for a short, consistent session",
        "sleep": "Start a simple bedtime wind-down routine",
    }.get(category, "Do a small version of your habit")


def _progressions_for_experience(level: str, critique: Optional[str]) -> List[Dict[str, Any]]:
    lowered_critique = (critique or "").lower()
    gentler = any(word in lowered_critique for word in ["smaller", "gentler", "easier", "less intense", "lighter"])
    tougher = any(word in lowered_critique for word in ["harder", "more ambitious", "more aggressive", "push more"])

    if gentler:
        return [
            {"week": 2, "description": "Keep the habit small and focus on consistency first"},
            {"week": 4, "description": "Add a modest increase only if the routine already feels easy"},
            {"week": 8, "description": "Settle into a sustainable version you can keep up"},
        ]
    if tougher or level == "advanced":
        return [
            {"week": 2, "description": "Increase the challenge slightly while keeping the plan consistent"},
            {"week": 4, "description": "Add another layer of difficulty or duration"},
            {"week": 8, "description": "Reach a strong but still sustainable target version"},
        ]
    if level == "intermediate":
        return [
            {"week": 2, "description": "Increase duration or structure a little once the routine feels stable"},
            {"week": 4, "description": "Add one meaningful progression without overloading the habit"},
            {"week": 8, "description": "Move toward your fuller target version if consistency is holding"},
        ]
    return [
        {"week": 2, "description": "Keep the first step small and repeatable"},
        {"week": 4, "description": "Increase duration slightly while keeping it manageable"},
        {"week": 8, "description": "Grow into a fuller version of the habit once the routine feels easy"},
    ]


def _mock_plan_json(user_goal: str, category: str, context: Optional[dict]) -> dict:
    ctx = _normalize_context(context)
    preferred_time = str(ctx.get("preferred_time", "flexible"))
    trigger_value = _preferred_time_default(preferred_time)
    schedule_text = _normalize_text(ctx.get("schedule_text"))
    schedule_days = _clean_schedule_days(ctx.get("schedule_days"))
    frequency_text = schedule_text or _canonical_frequency(ctx.get("frequency")) or user_goal
    frequency_type, frequency_pattern = _frequency_from_text(frequency_text)
    if schedule_days:
        frequency_type = "daily" if schedule_days == ORDERED_DAYS else "custom"
        frequency_pattern = None if schedule_days == ORDERED_DAYS else {"days": schedule_days}
    experience_level = _normalize_experience_level(ctx.get("experience_level")) or "beginner"
    habit_description = _normalize_text(ctx.get("habit_description"))
    duration_minutes = _duration_minutes_from_text(ctx.get("duration_minutes")) or 15
    critique = _normalize_text(ctx.get("critique"))

    requires_quantity = category in {"fitness", "study", "reading"}
    quantity_unit = "minutes" if requires_quantity else None

    description = _description_for_category(category, habit_description)
    if requires_quantity:
        description = f"{description} for about {duration_minutes} minutes"
    if critique and "more structured" in critique.lower():
        description = f"{description}. Keep the session clearly structured each time."
    if critique and "more variety" in critique.lower():
        description = f"{description}. Add a little variety so it stays engaging."

    return {
        "habit_name": _title_for_category(category),
        "category": category,
        "description": description,
        "trigger_type": "time",
        "trigger_value": trigger_value,
        "frequency_type": frequency_type,
        "frequency_pattern": frequency_pattern,
        "requires_quantity": requires_quantity,
        "quantity_unit": quantity_unit,
        "allows_notes": True,
        "motivation_statement": f"Start with a realistic version of: {user_goal}",
        "progressions": _progressions_for_experience(experience_level, critique),
    }


def _call_openai_messages_for_json(messages: Sequence[Dict[str, str]], model: str) -> dict:
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise AIPipelineConfigError("OPENAI_API_KEY is not configured")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIPipelineConfigError("openai package is not installed") from exc

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=list(messages),
            temperature=0.4,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise AIPipelineGenerationError(f"OpenAI request failed: {exc}") from exc

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise AIPipelineGenerationError("OpenAI returned an empty response")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIPipelineGenerationError("OpenAI response was not valid JSON") from exc


def _call_openai_for_json(prompt: str, model: str) -> dict:
    return _call_openai_messages_for_json(
        [
            {
                "role": "system",
                "content": "You generate concise habit plans and respond with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        model=model,
    )


def _clean_days(days: Any) -> Optional[dict]:
    if not isinstance(days, dict):
        return None
    raw_days = days.get("days")
    if not isinstance(raw_days, list):
        return None
    cleaned = []
    for day in raw_days:
        if not isinstance(day, str):
            continue
        name = day.strip().lower()
        if name in VALID_DAYS and name not in cleaned:
            cleaned.append(name)
    return {"days": cleaned} if cleaned else None


def _frequency_from_context_or_goal(user_goal: str, context: Optional[dict]) -> tuple[str, Optional[dict]]:
    ctx = _normalize_context(context)
    schedule_days = _clean_schedule_days(ctx.get("schedule_days"))
    if schedule_days:
        return ("daily", None) if schedule_days == ORDERED_DAYS else ("custom", {"days": schedule_days})
    schedule_text = _schedule_text_from_value(ctx.get("schedule_text"))
    if schedule_text:
        return _frequency_from_text(schedule_text)
    frequency_text = _canonical_frequency(ctx.get("frequency"))
    if frequency_text:
        return _frequency_from_text(frequency_text)
    return _frequency_from_text(user_goal)


def _normalize_llm_output(plan: HabitPlanLLMOutput, requested_category: str, user_goal: str, context: Optional[dict]) -> HabitPlanLLMOutput:
    plan.category = requested_category
    plan.trigger_type = "time"

    if not TIME_RE.match(plan.trigger_value or ""):
        preferred_time = str(_normalize_context(context).get("preferred_time", "flexible"))
        plan.trigger_value = _preferred_time_default(preferred_time)

    plan.frequency_type = (plan.frequency_type or "").lower()
    if plan.frequency_type not in {"daily", "custom"}:
        inferred_type, inferred_pattern = _frequency_from_context_or_goal(user_goal, context)
        plan.frequency_type = inferred_type
        plan.frequency_pattern = inferred_pattern

    if plan.frequency_type == "daily":
        plan.frequency_pattern = None
    else:
        cleaned = _clean_days(plan.frequency_pattern)
        if not cleaned:
            _, inferred_pattern = _frequency_from_context_or_goal(user_goal, context)
            plan.frequency_pattern = cleaned or inferred_pattern or {"days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
        else:
            plan.frequency_pattern = cleaned

    if not plan.motivation_statement:
        plan.motivation_statement = f"Consistent small steps make progress on: {user_goal}"

    return plan


def _to_habit_create(plan: HabitPlanLLMOutput) -> HabitCreate:
    return HabitCreate(
        name=plan.habit_name,
        category=plan.category,
        description=plan.description,
        trigger_type=plan.trigger_type,
        trigger_value=plan.trigger_value,
        frequency_type=plan.frequency_type,
        frequency_pattern=plan.frequency_pattern,
        requires_quantity=plan.requires_quantity,
        quantity_unit=plan.quantity_unit,
        allows_notes=plan.allows_notes,
        motivation_statement=plan.motivation_statement,
    )


def _generate_plan(prompt: str, user_goal: str, category: str, context: Optional[dict]) -> GeneratedHabitPlan:
    if category not in VALID_CATEGORIES:
        raise AIPipelineError(f"Unsupported category '{category}'")

    provider, model = _provider_and_model()
    if provider == "mock":
        raw_plan = _mock_plan_json(user_goal=user_goal, category=category, context=context)
    elif provider == "openai":
        raw_plan = _call_openai_for_json(prompt=prompt, model=model)
    else:
        raise AIPipelineConfigError(f"Unsupported AI_PROVIDER '{provider}'")

    try:
        plan = HabitPlanLLMOutput.model_validate(raw_plan)
    except Exception as exc:
        raise AIPipelineGenerationError(f"LLM JSON did not match expected shape: {exc}") from exc

    plan = _normalize_llm_output(plan, requested_category=category, user_goal=user_goal, context=context)
    habit_payload = _to_habit_create(plan)

    return GeneratedHabitPlan(
        habit_payload=habit_payload,
        progressions=[step.model_dump() for step in plan.progressions],
        raw_plan=plan.model_dump(),
        provider=provider,
        model=model,
    )


def generate_habit_plan(user_goal: str, category: str, context: Optional[dict] = None) -> GeneratedHabitPlan:
    prompt = _build_prompt(user_goal=user_goal, category=category, context=context)
    return _generate_plan(prompt=prompt, user_goal=user_goal, category=category, context=context)


def _draft_user_goal(draft: AIIntakeDraft) -> str:
    parts = [draft.goal_summary or ""]
    if draft.habit_description:
        parts.append(f"Habit details: {draft.habit_description}")
    if draft.frequency:
        parts.append(f"Desired frequency: {draft.frequency}")
    if draft.schedule_text:
        parts.append(f"Desired schedule: {draft.schedule_text}")
    if draft.duration_minutes:
        parts.append(f"Desired duration: {draft.duration_minutes} minutes")
    return ". ".join(part for part in parts if part)


def _draft_context(draft: AIIntakeDraft, critique: Optional[str] = None, current_plan: Optional[AIPlanSnapshot] = None) -> dict:
    context = {
        "experience_level": draft.experience_level or "beginner",
        "available_time": draft.available_time,
        "preferred_time": draft.preferred_time,
        "habit_description": draft.habit_description,
        "frequency": draft.frequency,
        "schedule_text": draft.schedule_text,
        "schedule_days": draft.schedule_days,
        "duration_minutes": draft.duration_minutes,
    }
    if critique:
        context["critique"] = critique
    if current_plan:
        context["current_plan"] = current_plan.model_dump()
    return context


def _validated_draft(draft: AIIntakeDraft) -> AIIntakeDraft:
    normalized_goal = _normalize_text(draft.goal_summary)
    normalized_description = _normalize_text(draft.habit_description)
    normalized_frequency = _canonical_frequency(draft.frequency)
    normalized_schedule_days = _clean_schedule_days(draft.schedule_days)
    normalized_schedule_text = _schedule_text_from_value(draft.schedule_text)
    if not normalized_schedule_days and normalized_schedule_text:
        normalized_schedule_days = _schedule_days_from_text(normalized_schedule_text)
    if not normalized_schedule_days and normalized_frequency:
        normalized_schedule_days = _schedule_days_from_text(normalized_frequency)
    if not normalized_schedule_text and normalized_schedule_days:
        normalized_schedule_text = _schedule_text_from_days(normalized_schedule_days)

    normalized = AIIntakeDraft(
        goal_summary=normalized_goal,
        habit_description=normalized_description,
        frequency=normalized_frequency,
        schedule_text=normalized_schedule_text,
        schedule_days=normalized_schedule_days,
        duration_minutes=_duration_minutes_from_text(draft.duration_minutes),
        experience_level=_normalize_experience_level(draft.experience_level),
        category=_normalize_category(
            draft.category,
            reference_text=" ".join(filter(None, [normalized_goal, normalized_description])),
        ),
        preferred_time="flexible",
        available_time=15,
    )
    if normalized.category is None:
        inferred_category, confident = _infer_category_from_text(" ".join(filter(None, [normalized.goal_summary, normalized.habit_description])))
        if confident:
            normalized.category = inferred_category
    return normalized


def missing_fields_for_draft(draft: AIIntakeDraft) -> List[str]:
    normalized = _validated_draft(draft)
    missing: List[str] = []
    if not normalized.goal_summary:
        missing.append("goal_summary")
    if not normalized.frequency:
        missing.append("frequency")
    if not normalized.schedule_days:
        missing.append("schedule")
    if not normalized.duration_minutes:
        missing.append("duration_minutes")
    if not normalized.experience_level:
        missing.append("experience_level")
    if not normalized.category:
        missing.append("category")
    return missing


def generate_habit_plan_from_draft(draft: AIIntakeDraft, critique: Optional[str] = None, current_plan: Optional[AIPlanSnapshot] = None) -> GeneratedHabitPlan:
    normalized_draft = _validated_draft(draft)
    missing_fields = missing_fields_for_draft(normalized_draft)
    if missing_fields:
        raise AIPipelineError(f"Draft is incomplete: {', '.join(missing_fields)}")

    user_goal = _draft_user_goal(normalized_draft)
    context = _draft_context(normalized_draft, critique=critique, current_plan=current_plan)
    prompt = _build_prompt(user_goal=user_goal, category=normalized_draft.category, context=context)
    return _generate_plan(prompt=prompt, user_goal=user_goal, category=normalized_draft.category, context=context)


def _is_short_acknowledgement(text: str) -> bool:
    return text.lower() in {"yes", "yep", "yeah", "ok", "okay", "sounds good", "looks good", "confirm"}


def _summarize_goal(text: str) -> str:
    stripped = text.strip().rstrip(".!?")
    if not stripped:
        return text
    parts = re.split(r"[.!?]", stripped)
    summary = parts[0].strip()
    return summary or stripped


def _extract_intake_update_mock(latest_user_message: str, current_draft: AIIntakeDraft) -> dict:
    message = _normalize_text(latest_user_message) or ""
    if not message or _is_short_acknowledgement(message):
        return {}

    lowered = message.lower()
    explicit_goal_change = any(
        phrase in lowered
        for phrase in ["i want", "my habit", "the habit", "goal is", "change the goal", "instead i want"]
    )
    category, confident = _infer_category_from_text(message)
    should_extract_goal = not current_draft.goal_summary or explicit_goal_change

    extraction = {
        "goal_summary": _summarize_goal(message) if should_extract_goal else None,
        "habit_description": message if should_extract_goal and len(message.split()) > 5 else None,
        "frequency": _canonical_frequency(message),
        "schedule_text": _schedule_text_from_value(message),
        "schedule_days": _schedule_days_from_text(message),
        "duration_minutes": _duration_minutes_from_text(message),
        "experience_level": _normalize_experience_level(message),
        "category": category,
        "category_confidence": "high" if confident else "low",
    }
    return extraction


def _extract_intake_update_openai(
    recent_messages: Sequence[AIChatMessage],
    current_draft: AIIntakeDraft,
    latest_user_message: str,
    model: str,
) -> dict:
    history = [
        {"role": message.role, "content": message.content}
        for message in recent_messages[-8:]
        if message.content.strip()
    ]

    prompt = f"""
Extract structured intake fields for a habit coaching conversation.

Current draft:
{json.dumps(current_draft.model_dump(), ensure_ascii=False)}

Latest user message:
{latest_user_message}

Return ONLY valid JSON with this shape:
{{
  "goal_summary": "string or null",
  "habit_description": "string or null",
  "frequency": "string or null",
  "schedule_text": "string or null",
  "schedule_days": ["monday"] or [],
  "duration_minutes": 20 or null,
  "experience_level": "beginner|intermediate|advanced|null",
  "category": "fitness|study|wellness|reading|sleep|null",
  "category_confidence": "low|medium|high"
}}

Rules:
- Only extract fields the user actually implied.
- If category is only weakly implied, leave category null or confidence low.
- Experience level must map to beginner, intermediate, advanced, or null.
- Frequency should stay as a plain-language phrase if present.
- schedule_days must only include concrete weekdays the user actually specified or strongly implied.
- If the user only said a count like "3 times a week" without days, leave schedule_days empty.
- duration_minutes should be an integer minute count when the user gave one.
""".strip()

    return _call_openai_messages_for_json(
        messages=[
            {
                "role": "system",
                "content": "You extract structured fields for a guided habit intake flow and return JSON only.",
            },
            *history,
            {"role": "user", "content": prompt},
        ],
        model=model,
    )


def _extract_intake_update(
    recent_messages: Sequence[AIChatMessage],
    current_draft: AIIntakeDraft,
    latest_user_message: str,
) -> dict:
    provider, model = _provider_and_model()
    if provider == "mock":
        return _extract_intake_update_mock(latest_user_message, current_draft)
    if provider == "openai":
        return _extract_intake_update_openai(recent_messages, current_draft, latest_user_message, model=model)
    raise AIPipelineConfigError(f"Unsupported AI_PROVIDER '{provider}'")


def _merged_draft(current_draft: AIIntakeDraft, extraction: dict, latest_user_message: str) -> AIIntakeDraft:
    try:
        extracted = IntakeExtractionLLMOutput.model_validate(extraction or {})
    except Exception:
        extracted = IntakeExtractionLLMOutput()

    reference_text = " ".join(filter(None, [latest_user_message, current_draft.goal_summary, current_draft.habit_description]))
    goal_summary = _normalize_text(extracted.goal_summary) or current_draft.goal_summary
    if not goal_summary and not _is_short_acknowledgement(latest_user_message):
        goal_summary = _summarize_goal(latest_user_message)

    habit_description = _normalize_text(extracted.habit_description) or current_draft.habit_description
    frequency = _canonical_frequency(extracted.frequency) or current_draft.frequency
    schedule_days = _clean_schedule_days(extracted.schedule_days) or current_draft.schedule_days
    schedule_text = _schedule_text_from_value(extracted.schedule_text) or current_draft.schedule_text
    if not schedule_days and schedule_text:
        schedule_days = _schedule_days_from_text(schedule_text)
    if not schedule_text and schedule_days:
        schedule_text = _schedule_text_from_days(schedule_days)
    if not schedule_days and frequency:
        schedule_days = _schedule_days_from_text(frequency)
    if not schedule_text and schedule_days:
        schedule_text = _schedule_text_from_days(schedule_days)
    duration_minutes = extracted.duration_minutes or current_draft.duration_minutes
    experience_level = _normalize_experience_level(extracted.experience_level) or current_draft.experience_level

    category: Optional[str] = current_draft.category
    extracted_category = _normalize_category(extracted.category, reference_text=reference_text)
    if extracted_category and (extracted.category_confidence or "").lower() in {"medium", "high"}:
        category = extracted_category
    if not category:
        inferred_category, confident = _infer_category_from_text(" ".join(filter(None, [goal_summary, habit_description, latest_user_message])))
        if confident:
            category = inferred_category

    return _validated_draft(
        AIIntakeDraft(
            goal_summary=goal_summary,
            habit_description=habit_description,
            frequency=frequency,
            schedule_text=schedule_text,
            schedule_days=schedule_days,
            duration_minutes=duration_minutes,
            experience_level=experience_level,
            category=category,
            preferred_time="flexible",
            available_time=15,
        )
    )


def _next_question(missing_fields: List[str]) -> str:
    if not missing_fields:
        return ""
    field = missing_fields[0]
    if field == "goal_summary":
        return "Tell me the habit you want to build and a short description of what that habit looks like for you."
    if field == "frequency":
        return "How often do you want to do this habit?"
    if field == "schedule":
        return "Which days of the week do you want to do it?"
    if field == "duration_minutes":
        return "How long should each session be?"
    if field == "experience_level":
        return "What’s your experience level with this habit: beginner, intermediate, or advanced?"
    if field == "category":
        return "What category fits best: fitness, study, wellness, reading, or sleep?"
    return "Tell me a little more."


def _confirmation_summary(draft: AIIntakeDraft) -> str:
    days_summary = "Every day" if draft.schedule_days == ORDERED_DAYS else ", ".join(day.title() for day in draft.schedule_days)
    duration_summary = f"{draft.duration_minutes} minute" if draft.duration_minutes == 1 else f"{draft.duration_minutes} minutes"
    lines = [
        "Here’s what I captured:",
        f"- Habit: {draft.goal_summary}",
    ]
    if draft.habit_description:
        lines.append(f"- Description: {draft.habit_description}")
    lines.append(f"- Frequency: {draft.frequency}")
    lines.append(f"- Days: {days_summary}")
    lines.append(f"- Duration: {duration_summary}")
    lines.append(f"- Experience level: {draft.experience_level}")
    lines.append(f"- Category: {draft.category}")
    return "\n".join(lines)


def process_intake_step(
    recent_messages: Sequence[AIChatMessage],
    current_draft: Optional[AIIntakeDraft],
    latest_user_message: str,
) -> IntakeStepResult:
    base_draft = _validated_draft(current_draft or AIIntakeDraft())
    extraction = _extract_intake_update(recent_messages=recent_messages, current_draft=base_draft, latest_user_message=latest_user_message)
    updated_draft = _merged_draft(base_draft, extraction=extraction, latest_user_message=latest_user_message)

    missing_fields = missing_fields_for_draft(updated_draft)
    ready_for_confirmation = not missing_fields
    confirmation_summary = _confirmation_summary(updated_draft) if ready_for_confirmation else None

    required_field_changed = any(
        getattr(base_draft, field) != getattr(updated_draft, field)
        for field in ["goal_summary", "frequency", "schedule_text", "schedule_days", "duration_minutes", "experience_level", "category"]
    )
    needs_clarification = bool(latest_user_message.strip()) and not required_field_changed and not ready_for_confirmation

    if ready_for_confirmation:
        assistant_message = f"{confirmation_summary}\n\nIf that looks right, confirm and I’ll generate your plan."
    elif needs_clarification:
        assistant_message = f"I still need one more detail. {_next_question(missing_fields)}"
    else:
        assistant_message = _next_question(missing_fields)

    return IntakeStepResult(
        assistant_message=assistant_message,
        updated_draft=updated_draft,
        missing_fields=missing_fields,
        ready_for_confirmation=ready_for_confirmation,
        confirmation_summary=confirmation_summary,
        needs_clarification=needs_clarification,
    )


def revise_habit_plan(
    draft: AIIntakeDraft,
    current_plan: AIPlanSnapshot,
    critique: str,
    recent_messages: Sequence[AIChatMessage],
) -> RevisionResult:
    provider, model = _provider_and_model()
    updated_intake = process_intake_step(
        recent_messages=recent_messages,
        current_draft=draft,
        latest_user_message=critique,
    )

    normalized_original = _validated_draft(draft)
    normalized_updated = _validated_draft(updated_intake.updated_draft)
    changed_required_fields = any(
        getattr(normalized_original, field) != getattr(normalized_updated, field)
        for field in ["goal_summary", "frequency", "schedule_text", "schedule_days", "duration_minutes", "experience_level", "category"]
    )

    if changed_required_fields:
        return RevisionResult(
            action="reopen_intake",
            provider=provider,
            model=model,
            reopen_intake=updated_intake,
        )

    revised_plan = generate_habit_plan_from_draft(
        normalized_updated,
        critique=critique,
        current_plan=current_plan,
    )
    return RevisionResult(
        action="plan_tweak",
        provider=revised_plan.provider,
        model=revised_plan.model,
        plan_tweak=revised_plan,
    )
