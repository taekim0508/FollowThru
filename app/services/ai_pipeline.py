from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from ..config import settings
from ..models import AIChatMessage, AIHabitCandidate, AIIntakeDraft, AIPlanSnapshot, HabitCreate


TIME_RE = re.compile(r"^\d{2}:\d{2}$")
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
VALID_SCHEDULE_MODES = {"daily", "weekdays", "weekends", "specific_days", "times_per_week"}
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

_TRACKED_PATTERNS: List[tuple] = [
    # (regex, target_group, unit)
    (re.compile(r"(\d+(?:\.\d+)?)\s*km", re.I),       1, "km"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*miles?", re.I),   1, "miles"),
    (re.compile(r"(\d+)\s*pages?", re.I),              1, "pages"),
    (re.compile(r"(\d+)\s*glasses?", re.I),            1, "glasses"),
    (re.compile(r"(\d+)\s*(?:cups?|liters?|litres?|oz)", re.I), 1, "glasses"),
    (re.compile(r"(\d+)\s*reps?", re.I),               1, "reps"),
    (re.compile(r"(\d+)\s*push\s*ups?", re.I),         1, "reps"),
    (re.compile(r"(\d+)\s*sit\s*ups?", re.I),          1, "reps"),
    (re.compile(r"(\d+)\s*calories?", re.I),           1, "calories"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*lbs?", re.I),     1, "lbs"),
]

_BINARY_KEYWORDS: frozenset = frozenset([
    "meditate", "meditation", "journal", "journaling", "stretch", "stretching",
    "pray", "prayer", "reflect", "reflection", "breathe", "breathing",
    "cold shower", "no phone", "screen-free", "gratitude", "affirmation",
    "sleep", "wake up", "wind down", "read", "reading",
])


def _infer_habit_type_from_text(text: str) -> tuple:
    """Return (habit_type, target_value, quantity_unit) inferred from goal text."""
    lowered = text.lower()
    for pattern, group, unit in _TRACKED_PATTERNS:
        m = pattern.search(lowered)
        if m:
            return "tracked", float(m.group(group)), unit
    if any(kw in lowered for kw in _BINARY_KEYWORDS):
        return "binary", None, None
    return "binary", None, None


_HABIT_KEYWORD_MAP: Dict[str, List[str]] = {
    "fitness": ["run", "running", "jog", "walk", "movement", "move more", "work out", "workout", "exercise", "gym", "lift", "yoga", "cycle", "swim", "swimming", "hike", "hiking"],
    "study": ["study", "learn", "practice coding", "homework", "exam", "class", "course", "read textbook", "flashcard"],
    "wellness": ["meditate", "meditation", "pray", "prayer", "journal", "journaling", "reflect", "reflection", "mindful", "wellness", "breathe", "breathing"],
    "reading": ["read", "reading", "book", "pages", "novel", "chapter"],
    "sleep": ["sleep", "bedtime", "wind down", "wind-down", "go to bed", "night routine", "wake up"],
}

MAX_RECENT_MESSAGES = 10
MAX_PLAN_RETRIES = 2

SENSITIVE_KEYWORDS: frozenset = frozenset([
    "surgery", "injury", "injured", "recovering", "recovery from",
    "diagnosed", "diagnosis", "chronic condition", "disability",
    "depressed", "depression", "anxiety disorder", "suicidal", "self-harm", "self harm",
    "eating disorder", "anorexia", "bulimia",
    "addiction", "alcoholic",
    "500 calories", "400 calories", "300 calories",
])

OFF_TOPIC_PHRASES: frozenset = frozenset([
    "write code", "debug this", "fix my code", "write a function",
    "what is the weather", "will it rain", "temperature outside",
    "capital of", "who invented", "what year was",
    "movie recommendation", "tv show recommendation", "what should i watch",
    "order pizza", "best restaurant", "recommend a restaurant",
    "tell me a joke", "write me a poem", "translate this",
    "stock price", "cryptocurrency",
])

MULTI_HABIT_PATTERNS: List = [
    re.compile(r"\band\s+(?:also\s+)?(?:i\s+(?:also\s+)?want|i\s+also|want\s+to)\b", re.IGNORECASE),
    re.compile(r"\bas\s+well\s+as\b", re.IGNORECASE),
    re.compile(r"\bin\s+addition\b", re.IGNORECASE),
    re.compile(r"\balso\s+(?:want|plan|trying)\b", re.IGNORECASE),
]

REALISM_CAPS: Dict[str, Dict[str, Dict[str, int]]] = {
    "fitness": {
        "beginner":     {"max_duration_minutes": 60,  "max_days_per_week": 5},
        "intermediate": {"max_duration_minutes": 90,  "max_days_per_week": 6},
        "advanced":     {"max_duration_minutes": 180, "max_days_per_week": 7},
    },
    "study": {
        "beginner":     {"max_duration_minutes": 120, "max_days_per_week": 7},
        "intermediate": {"max_duration_minutes": 240, "max_days_per_week": 7},
        "advanced":     {"max_duration_minutes": 360, "max_days_per_week": 7},
    },
    "wellness": {
        "beginner":     {"max_duration_minutes": 60,  "max_days_per_week": 7},
        "intermediate": {"max_duration_minutes": 90,  "max_days_per_week": 7},
        "advanced":     {"max_duration_minutes": 120, "max_days_per_week": 7},
    },
    "reading": {
        "beginner":     {"max_duration_minutes": 90,  "max_days_per_week": 7},
        "intermediate": {"max_duration_minutes": 120, "max_days_per_week": 7},
        "advanced":     {"max_duration_minutes": 180, "max_days_per_week": 7},
    },
    "sleep": {
        "beginner":     {"max_duration_minutes": 60, "max_days_per_week": 7},
        "intermediate": {"max_duration_minutes": 60, "max_days_per_week": 7},
        "advanced":     {"max_duration_minutes": 90, "max_days_per_week": 7},
    },
}

# When experience level + category are known, these are sensible starting defaults
# for frequency (days/week) to infer when frequency is not yet specified
EXPERIENCE_FREQUENCY_DEFAULTS: Dict[str, Dict[str, int]] = {
    "fitness":  {"beginner": 3, "intermediate": 4, "advanced": 5},
    "study":    {"beginner": 5, "intermediate": 5, "advanced": 6},
    "wellness": {"beginner": 7, "intermediate": 7, "advanced": 7},
    "reading":  {"beginner": 5, "intermediate": 6, "advanced": 7},
    "sleep":    {"beginner": 7, "intermediate": 7, "advanced": 7},
}

EXPERIENCE_DURATION_DEFAULTS: Dict[str, Dict[str, int]] = {
    "fitness":  {"beginner": 20, "intermediate": 30, "advanced": 45},
    "study":    {"beginner": 25, "intermediate": 45, "advanced": 60},
    "wellness": {"beginner": 10, "intermediate": 15, "advanced": 20},
    "reading":  {"beginner": 15, "intermediate": 20, "advanced": 30},
    "sleep":    {"beginner": 15, "intermediate": 20, "advanced": 30},
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
    duration_minutes: Optional[int] = None  # filled by ambitious variant prompt; ignored for balanced


class IntakeExtractionLLMOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    goal_summary: Optional[str] = None
    habit_description: Optional[str] = None
    frequency: Optional[str] = None
    schedule_mode: Optional[str] = None
    times_per_week: Optional[int] = None
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
    conflict_fields: List[str]
    ready_for_confirmation: bool
    confirmation_summary: Optional[str]
    needs_clarification: bool
    needs_correction: bool = False
    intent: str = "on_topic"
    realism_warning: Optional[str] = None


@dataclass
class RevisionResult:
    action: str
    provider: str
    model: str
    plan_tweak: Optional[GeneratedHabitPlan] = None
    reopen_intake: Optional[IntakeStepResult] = None


@dataclass
class RealistCheckResult:
    is_realistic: bool
    warning_message: Optional[str]
    suggested_duration_minutes: Optional[int] = None
    suggested_days_per_week: Optional[int] = None


@dataclass
class HabitProposalResult:
    action: str
    provider: str
    model: str
    assistant_message: str
    what_i_heard: Optional[str]
    candidates: List[AIHabitCandidate]
    needs_clarification: bool


@dataclass
class CandidateRefinementResult:
    provider: str
    model: str
    assistant_message: str
    candidate: AIHabitCandidate


def _count_per_week_from_text(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return max(1, min(value, 7))

    text = (_normalize_text(value) or "").lower()
    if not text:
        return None

    digit_match = re.search(r"\b(\d+)\s*(?:x|times?)\s*(?:a|per)?\s*week\b", text)
    if digit_match:
        return max(1, min(int(digit_match.group(1)), 7))

    word_match = re.search(r"\b([a-z-]+)\s*(?:x|times?)\s*(?:a|per)?\s*week\b", text)
    if word_match:
        number = _number_from_words(word_match.group(1))
        if number is not None:
            return max(1, min(number, 7))

    if "once a week" in text:
        return 1
    if "twice a week" in text:
        return 2
    return None


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

    beginner_markers = [
        "beginner", "new to", "novice", "never", "first time", "just starting", "starting out",
        "fresh start", "from scratch", "haven't done", "haven't tried", "brand new",
        "no experience", "not done this", "not tried",
    ]
    intermediate_markers = [
        "intermediate", "some experience", "on and off", "used to", "have done this before",
        "done it before", "tried it before", "tried it a few", "done it a bit", "done it a couple",
        "done this before", "here and there", "occasionally", "sometimes do", "a little experience",
        "a bit of experience", "few times", "a few times", "dabbled",
    ]
    advanced_markers = [
        "advanced", "experienced", "expert", "for years", "very comfortable", "already consistent",
        "consistently do", "do it regularly", "do this regularly", "been doing", "been running",
        "long time", "daily for", "weeks of", "months of",
    ]

    if any(marker in text for marker in beginner_markers):
        return "beginner"
    if any(marker in text for marker in intermediate_markers):
        return "intermediate"
    if any(marker in text for marker in advanced_markers):
        return "advanced"
    return None


def _infer_category_from_text(text: str) -> tuple[Optional[str], bool]:
    lowered = text.lower()
    matches = [cat for cat, keywords in _HABIT_KEYWORD_MAP.items() if any(kw in lowered for kw in keywords)]
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

    count_per_week = _count_per_week_from_text(text)
    if count_per_week:
        return f"{count_per_week} times per week"

    explicit_days = [day for day in ORDERED_DAYS if day in text]
    if explicit_days:
        ordered = [day for day in ORDERED_DAYS if day in explicit_days]
        return ", ".join(ordered)

    if any(phrase in text for phrase in ["once a week", "twice a week", "every other day", "every morning", "every evening"]):
        return _normalize_text(value)

    return None


_ALL_DAYS_PATTERN = {"days": list(ORDERED_DAYS)}


def _frequency_from_text(text: str) -> tuple[str, Optional[dict]]:
    lowered = text.lower()
    if "every day" in lowered or "daily" in lowered or "each day" in lowered:
        return "daily", _ALL_DAYS_PATTERN
    if any(phrase in lowered for phrase in ["weekday", "weekdays", "monday to friday", "mon-fri", "except weekends"]):
        return "custom", {"days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
    if "weekend" in lowered:
        return "custom", {"days": ["saturday", "sunday"]}

    explicit_days = [day for day in ORDERED_DAYS if day in lowered]
    if explicit_days:
        return "custom", {"days": explicit_days}

    count = _count_per_week_from_text(lowered)
    if count:
        day_sets = {
            1: ["monday"],
            2: ["monday", "thursday"],
            3: ["monday", "wednesday", "friday"],
            4: ["monday", "tuesday", "thursday", "friday"],
            5: ["monday", "tuesday", "wednesday", "thursday", "friday"],
            6: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
            7: list(ORDERED_DAYS),
        }
        days = day_sets[count]
        return ("daily", _ALL_DAYS_PATTERN) if len(days) == 7 else ("custom", {"days": days})

    return "daily", _ALL_DAYS_PATTERN


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
    if _count_per_week_from_text(frequency):
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


def classify_intent_mock(message: str) -> str:
    """Rule-based intent classification for use in mock/test mode."""
    lowered = message.lower()

    if any(kw in lowered for kw in SENSITIVE_KEYWORDS):
        return "sensitive"

    if any(phrase in lowered for phrase in OFF_TOPIC_PHRASES):
        return "off_topic"

    # Multi-habit: conjunction present AND multiple distinct habit categories hit
    if any(pat.search(lowered) for pat in MULTI_HABIT_PATTERNS):
        cat_hits = sum(1 for kws in _HABIT_KEYWORD_MAP.values() if any(kw in lowered for kw in kws))
        if cat_hits >= 2:
            return "multi_habit"

    return "on_topic"


def classify_intent_openai(message: str, recent_messages: Sequence[AIChatMessage], model: str) -> str:
    """LLM-based intent classification. Falls back to on_topic on any error."""
    history = [
        {"role": m.role, "content": m.content}
        for m in recent_messages[-4:]
        if m.content.strip()
    ]
    prompt = (
        f'Classify this user message in a habit coaching app.\n\nMessage: "{message}"\n\n'
        'Return ONLY valid JSON: {"intent": "<label>"}\n\n'
        "Labels:\n"
        "- on_topic: discussing a habit to build (including emotional/motivational context)\n"
        "- off_topic: completely unrelated to habits or self-improvement\n"
        "- sensitive: mentions medical conditions, injury recovery, mental health concerns, "
        "eating disorders, or substance abuse\n"
        "- multi_habit: user mentions 2 or more distinct habits they want to build simultaneously"
    )
    try:
        result = _call_openai_messages_for_json(
            messages=[
                {"role": "system", "content": "Classify user intent and return JSON only."},
                *history,
                {"role": "user", "content": prompt},
            ],
            model=model,
        )
        intent = str(result.get("intent", "on_topic")).lower()
        return intent if intent in {"on_topic", "off_topic", "sensitive", "multi_habit"} else "on_topic"
    except Exception:
        return "on_topic"


def classify_intent(message: str, recent_messages: Sequence[AIChatMessage]) -> str:
    """Classify the intent of a user message. Returns one of: on_topic, off_topic, sensitive, multi_habit."""
    provider, model = _provider_and_model()
    if provider == "mock":
        return classify_intent_mock(message)
    if provider == "openai":
        return classify_intent_openai(message, recent_messages, model)
    return "on_topic"


def check_realism(draft: "AIIntakeDraft") -> RealistCheckResult:
    """Rule-based realism check. Returns a warning if the draft contains an unrealistic goal."""
    exp = draft.experience_level
    cat = draft.category
    if not exp or not cat or exp not in VALID_EXPERIENCE_LEVELS or cat not in REALISM_CAPS:
        return RealistCheckResult(is_realistic=True, warning_message=None)

    caps = REALISM_CAPS[cat][exp]
    max_duration = caps["max_duration_minutes"]
    max_days = caps["max_days_per_week"]

    issues: List[str] = []
    suggested_duration: Optional[int] = None
    suggested_days: Optional[int] = None

    if draft.duration_minutes and draft.duration_minutes > max_duration:
        suggested_duration = max_duration
        issues.append(f"sessions of {draft.duration_minutes} minutes")

    days_count = len(draft.schedule_days) if draft.schedule_days else None
    if days_count and days_count > max_days:
        suggested_days = max_days
        issues.append(f"{days_count} days per week")

    if not issues:
        return RealistCheckResult(is_realistic=True, warning_message=None)

    issue_text = " and ".join(issues)
    parts = [f"That's ambitious! {issue_text.capitalize()} can be a lot to start with as a {exp}."]
    suggestions: List[str] = []
    if suggested_duration:
        suggestions.append(f"sessions up to {_format_duration(suggested_duration)}")
    if suggested_days:
        suggestions.append(f"{suggested_days} days per week")
    if suggestions:
        parts.append(f"I'd suggest starting with {' and '.join(suggestions)} to build consistency first.")
    parts.append("Want me to keep your original goal, or adjust it to something more manageable?")

    return RealistCheckResult(
        is_realistic=False,
        warning_message=" ".join(parts),
        suggested_duration_minutes=suggested_duration,
        suggested_days_per_week=suggested_days,
    )


def _infer_defaults_from_experience(draft: "AIIntakeDraft") -> "AIIntakeDraft":
    """
    When both experience level and category are known, fill in sensible frequency/duration
    defaults for any fields that are still missing. This reduces the number of clarifying
    questions the user has to answer.
    """
    exp = draft.experience_level
    cat = draft.category
    if not exp or not cat or exp not in VALID_EXPERIENCE_LEVELS or cat not in EXPERIENCE_FREQUENCY_DEFAULTS:
        return draft

    duration = draft.duration_minutes
    schedule_days = list(draft.schedule_days or [])
    frequency = draft.frequency
    schedule_text = draft.schedule_text

    changed = False

    # Fill in duration if missing
    if not duration:
        duration = EXPERIENCE_DURATION_DEFAULTS[cat][exp]
        changed = True

    # Fill in frequency/schedule if both are missing
    if not frequency and not schedule_days:
        days_count = EXPERIENCE_FREQUENCY_DEFAULTS[cat][exp]
        day_sets: Dict[int, List[str]] = {
            3: ["monday", "wednesday", "friday"],
            4: ["monday", "tuesday", "thursday", "friday"],
            5: ["monday", "tuesday", "wednesday", "thursday", "friday"],
            6: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
            7: list(ORDERED_DAYS),
        }
        schedule_days = day_sets.get(days_count, ["monday", "wednesday", "friday"])
        frequency = "every day" if days_count == 7 else f"{days_count} times per week"
        schedule_text = _schedule_text_from_days(schedule_days)
        changed = True

    # Infer habit_type from goal text when not already set
    habit_type = draft.habit_type or "binary"
    target_value = draft.target_value
    quantity_unit = draft.quantity_unit
    if not draft.target_value:
        combined = " ".join(filter(None, [draft.goal_summary, draft.habit_description]))
        if combined:
            inferred_type, inferred_target, inferred_unit = _infer_habit_type_from_text(combined)
            if inferred_type == "tracked":
                habit_type = "tracked"
                target_value = inferred_target
                quantity_unit = inferred_unit
                changed = True

    if not changed:
        return draft

    return AIIntakeDraft(
        goal_summary=draft.goal_summary,
        habit_description=draft.habit_description,
        frequency=frequency,
        schedule_text=schedule_text,
        schedule_days=schedule_days,
        duration_minutes=duration,
        experience_level=draft.experience_level,
        category=draft.category,
        preferred_time=draft.preferred_time,
        available_time=draft.available_time,
        motivation_statement=draft.motivation_statement,
        habit_type=habit_type,
        target_value=target_value,
        quantity_unit=quantity_unit,
    )


def _validate_plan_fields(plan: HabitPlanLLMOutput) -> List[str]:
    """Validate a generated plan and return a list of error strings (empty = valid)."""
    errors: List[str] = []
    if not (plan.habit_name or "").strip():
        errors.append("habit_name is empty")
    if not TIME_RE.match(plan.trigger_value or ""):
        errors.append(f"trigger_value '{plan.trigger_value}' is not valid HH:MM format")
    freq_type = (plan.frequency_type or "").lower()
    if freq_type not in {"daily", "custom"}:
        errors.append(f"frequency_type '{plan.frequency_type}' must be 'daily' or 'custom'")
    if freq_type == "custom":
        days = (plan.frequency_pattern or {}).get("days")
        if not isinstance(days, list) or not days:
            errors.append("frequency_pattern.days must be a non-empty list when frequency_type is 'custom'")
        elif not all(isinstance(d, str) and d.lower() in VALID_DAYS for d in days):
            errors.append("frequency_pattern.days contains invalid day names")
    if not (plan.motivation_statement or "").strip():
        errors.append("motivation_statement is empty")
    if not plan.progressions:
        errors.append("progressions must have at least one step")
    return errors


def _normalize_schedule_mode(value: Any) -> Optional[str]:
    text = (_normalize_text(value) or "").lower()
    if not text:
        return None
    alias_map = {
        "daily": "daily",
        "every day": "daily",
        "weekdays": "weekdays",
        "weekday": "weekdays",
        "weekends": "weekends",
        "weekend": "weekends",
        "specific days": "specific_days",
        "specific_days": "specific_days",
        "specific days only": "specific_days",
        "times per week": "times_per_week",
        "times_per_week": "times_per_week",
        "x times per week": "times_per_week",
    }
    if text in alias_map:
        return alias_map[text]
    if any(phrase in text for phrase in ["every day", "daily", "each day"]):
        return "daily"
    if any(phrase in text for phrase in ["weekday", "weekdays", "monday to friday", "mon-fri", "except weekends"]):
        return "weekdays"
    if "weekend" in text:
        return "weekends"
    if _count_per_week_from_text(text):
        return "times_per_week"
    if any(day in text for day in ORDERED_DAYS):
        return "specific_days"
    return text if text in VALID_SCHEDULE_MODES else None


def _canonical_days_for_mode(mode: Optional[str]) -> List[str]:
    if mode == "daily":
        return ORDERED_DAYS.copy()
    if mode == "weekdays":
        return ORDERED_DAYS[:5]
    if mode == "weekends":
        return ORDERED_DAYS[5:]
    return []


def _derived_frequency(mode: Optional[str], times_per_week: Optional[int], schedule_days: List[str]) -> Optional[str]:
    if mode == "daily":
        return "every day"
    if mode == "weekdays":
        return "weekdays"
    if mode == "weekends":
        return "weekends"
    if mode == "times_per_week" and times_per_week:
        return f"{times_per_week} times per week"
    if schedule_days:
        return ", ".join(schedule_days)
    return None


def _derived_schedule_text(mode: Optional[str], times_per_week: Optional[int], schedule_days: List[str]) -> Optional[str]:
    if mode == "daily":
        return "every day"
    if mode == "weekdays":
        return "weekdays"
    if mode == "weekends":
        return "weekends"
    if schedule_days:
        return ", ".join(schedule_days)
    if mode == "times_per_week" and times_per_week:
        return f"{times_per_week} times per week"
    return None


def _first_conflict(draft: AIIntakeDraft) -> tuple[List[str], Optional[str]]:
    days = draft.schedule_days
    mode = draft.schedule_mode

    if mode == "times_per_week" and draft.times_per_week and days and len(days) != draft.times_per_week:
        return (
            ["times_per_week", "schedule_days"],
            f"You said {draft.times_per_week} times per week, but you selected {len(days)} days. Pick {draft.times_per_week} days or change the weekly count.",
        )

    if mode == "weekdays" and days and days != ORDERED_DAYS[:5]:
        return (
            ["schedule_mode", "schedule_days"],
            "You picked weekdays, but the selected days do not match weekdays. Keep weekdays or switch to specific days.",
        )

    if mode == "weekends" and days and days != ORDERED_DAYS[5:]:
        return (
            ["schedule_mode", "schedule_days"],
            "You picked weekends, but the selected days do not match weekends. Keep weekends or switch to specific days.",
        )

    if mode == "daily" and days and days != ORDERED_DAYS:
        return (
            ["schedule_mode", "schedule_days"],
            "You picked every day, but the selected days do not cover the full week. Keep every day or switch to specific days.",
        )

    return ([], None)


def _build_prompt(user_goal: str, category: str, context: Optional[dict]) -> str:
    ctx = _normalize_context(context)
    exp = ctx.get("experience_level", "beginner")
    available_time = ctx.get("available_time", 15)
    preferred_time = ctx.get("preferred_time", "flexible")
    habit_description = ctx.get("habit_description")
    frequency = ctx.get("frequency")
    schedule_mode = ctx.get("schedule_mode")
    times_per_week = ctx.get("times_per_week")
    schedule_text = ctx.get("schedule_text")
    schedule_days = ctx.get("schedule_days")
    duration_minutes = ctx.get("duration_minutes")
    critique = ctx.get("critique")
    current_plan = ctx.get("current_plan")
    variant = ctx.get("variant", "balanced")
    balanced_duration = ctx.get("balanced_duration")
    balanced_days = ctx.get("balanced_days")

    habit_type = ctx.get("habit_type", "binary")
    user_motivation = ctx.get("user_motivation")
    target_value = ctx.get("target_value")
    quantity_unit = ctx.get("quantity_unit")

    extra_sections = []
    if habit_description:
        extra_sections.append(f'Habit Description: "{habit_description}"')
    if user_motivation:
        extra_sections.append(f'User Motivation: "{user_motivation}"')
    if habit_type == "tracked" and target_value is not None:
        unit_label = quantity_unit or "units"
        extra_sections.append(f"Habit Type: tracked — target {target_value} {unit_label} per session")
    if frequency:
        extra_sections.append(f'Desired Frequency: "{frequency}"')
    if schedule_mode:
        extra_sections.append(f'Desired Schedule Mode: "{schedule_mode}"')
    if times_per_week:
        extra_sections.append(f"Desired Times Per Week: {times_per_week}")
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

    # --- Ambitious variant: few-shot step-up guidance ---
    if variant == "ambitious":
        bal_days_str = ", ".join(balanced_days) if balanced_days else "not specified"
        ambitious_section = f"""
VARIANT: AMBITIOUS
This is the ambitious version of the habit. The balanced version has:
- Duration: {_format_duration(balanced_duration) if balanced_duration else "not set"}
- Schedule: {bal_days_str}

Your task: design a step-up that is noticeably more challenging but still realistic for
someone at the {exp} level. The frequency has already been set to {times_per_week or "the schedule above"} — use that.
Focus on choosing the right duration. Do NOT jump to maximum effort.

Calibration examples (use these as a guide, not rigid rules):
- Meditation, 10 min balanced → 15 min ambitious (+5 min; small habit, modest add)
- Meditation, 20 min balanced → 28 min ambitious (+8 min)
- Journaling, 10 min balanced → 15 min ambitious (+5 min)
- Running, 15 min balanced → 30 min ambitious (+15 min; short start, bigger room to grow)
- Running, 25 min balanced → 40 min ambitious (+15 min)
- Running, 40 min balanced → 52 min ambitious (+12 min; already substantial)
- Running, 50 min balanced → 62 min ambitious (+12 min; don't pile on too much)
- Strength training, 20 min balanced → 35 min ambitious (+15 min)
- Strength training, 35 min balanced → 50 min ambitious (+15 min)
- Strength training, 50 min balanced → 60 min ambitious (+10 min)
- Yoga, 30 min balanced → 45 min ambitious (+15 min)
- Reading, 15 min balanced → 25 min ambitious (+10 min)
- Reading, 30 min balanced → 40 min ambitious (+10 min)

Key principles:
- Shorter balanced durations get larger increments; longer ones get smaller increments.
- Meditation/journaling/breathing: cap increment at ~10 min.
- Fitness/strength/running: increment can be 12-20 min for short-to-mid balanced durations.
- Never exceed what's realistic: a beginner's ambitious run shouldn't exceed 60 min.

Output "duration_minutes" in the JSON with your chosen ambitious duration.
""".strip()
    else:
        ambitious_section = ""

    duration_output_field = '"duration_minutes": <integer>,' if variant == "ambitious" else ""

    return f"""
You are a habit formation coach. Generate a practical habit plan.

User Goal: "{user_goal}"
Category: {category}
{extra_block}Experience Level: {exp}
Available Time (minutes): {available_time}
Preferred Time: {preferred_time}
{ambitious_section}

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
  "motivation_statement": "string",{duration_output_field}
  "progressions": [
    {{"week": 2, "description": "string"}},
    {{"week": 4, "description": "string"}}
  ]
}}

Rules:
- Do not promise specific outcomes (weight loss, performance gains, etc.).
- Do not cite specific statistics or research studies.
- Start small for the user's experience level:
  * beginner: 2-3 sessions per week, 15-25 minutes each.
  * intermediate: 3-4 sessions per week, 25-40 minutes each.
  * advanced: 4-5 sessions per week, 40-60 minutes each.
- The desired frequency and duration, if provided, take priority over these defaults.
- Respect the desired schedule and duration if they are provided.
- Progressions should increase gradually — each step must be harder than the previous.
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
    schedule_mode = _normalize_schedule_mode(ctx.get("schedule_mode"))
    times_per_week = _count_per_week_from_text(ctx.get("times_per_week"))
    schedule_text = _normalize_text(ctx.get("schedule_text"))
    schedule_days = _clean_schedule_days(ctx.get("schedule_days"))
    if not schedule_days and schedule_mode in {"daily", "weekdays", "weekends"}:
        schedule_days = _canonical_days_for_mode(schedule_mode)
    frequency_text = (
        _derived_frequency(schedule_mode, times_per_week, schedule_days)
        or schedule_text
        or _canonical_frequency(ctx.get("frequency"))
        or user_goal
    )
    frequency_type, frequency_pattern = _frequency_from_text(frequency_text)
    if schedule_days:
        frequency_type = "daily" if schedule_days == ORDERED_DAYS else "custom"
        frequency_pattern = {"days": list(ORDERED_DAYS)} if schedule_days == ORDERED_DAYS else {"days": schedule_days}
    experience_level = _normalize_experience_level(ctx.get("experience_level")) or "beginner"
    habit_description = _normalize_text(ctx.get("habit_description"))
    duration_minutes = _duration_minutes_from_text(ctx.get("duration_minutes")) or 15
    critique = _normalize_text(ctx.get("critique"))

    requires_quantity = category in {"fitness", "study", "reading"}
    quantity_unit = "minutes" if requires_quantity else None

    description = _description_for_category(category, habit_description)
    if requires_quantity:
        description = f"{description} for about {_format_duration(duration_minutes)}"
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
    schedule_mode = _normalize_schedule_mode(ctx.get("schedule_mode"))
    schedule_days = _clean_schedule_days(ctx.get("schedule_days"))
    if not schedule_days and schedule_mode in {"daily", "weekdays", "weekends"}:
        schedule_days = _canonical_days_for_mode(schedule_mode)
    if schedule_days:
        return ("daily", None) if schedule_days == ORDERED_DAYS else ("custom", {"days": schedule_days})
    derived_frequency = _derived_frequency(schedule_mode, _count_per_week_from_text(ctx.get("times_per_week")), schedule_days)
    if derived_frequency:
        return _frequency_from_text(derived_frequency)
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
        plan.frequency_pattern = {"days": list(ORDERED_DAYS)}
    else:
        cleaned = _clean_days(plan.frequency_pattern)
        if not cleaned:
            _, inferred_pattern = _frequency_from_context_or_goal(user_goal, context)
            plan.frequency_pattern = cleaned or inferred_pattern or {"days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
        else:
            plan.frequency_pattern = cleaned

    if not plan.motivation_statement:
        plan.motivation_statement = f"Consistent small steps make progress on: {user_goal}"

    # Override with user-stated motivation if present in context
    user_motivation = _normalize_context(context).get("user_motivation")
    if user_motivation:
        plan.motivation_statement = user_motivation

    # Override habit_type / target / unit with user-stated values if present
    ctx = _normalize_context(context)
    if ctx.get("habit_type") == "tracked":
        plan.requires_quantity = True
        if ctx.get("target_value") is not None:
            plan.target_value = ctx["target_value"]
        if ctx.get("quantity_unit"):
            plan.quantity_unit = ctx["quantity_unit"]

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
        habit_type="tracked" if plan.requires_quantity else "binary",
        target_value=getattr(plan, "target_value", None),
        requires_quantity=plan.requires_quantity,
        quantity_unit=plan.quantity_unit,
        allows_notes=plan.allows_notes,
        motivation_statement=plan.motivation_statement,
    )


def _generate_plan(prompt: str, user_goal: str, category: str, context: Optional[dict]) -> GeneratedHabitPlan:
    if category not in VALID_CATEGORIES:
        raise AIPipelineError(f"Unsupported category '{category}'")

    provider, model = _provider_and_model()
    last_validation_errors: Optional[str] = None

    for attempt in range(MAX_PLAN_RETRIES + 1):
        if provider == "mock":
            raw_plan = _mock_plan_json(user_goal=user_goal, category=category, context=context)
        elif provider == "openai":
            retry_prompt = prompt
            if last_validation_errors and attempt > 0:
                retry_prompt = f"{prompt}\n\nPrevious attempt had validation errors — fix them:\n{last_validation_errors}"
            raw_plan = _call_openai_for_json(prompt=retry_prompt, model=model)
        else:
            raise AIPipelineConfigError(f"Unsupported AI_PROVIDER '{provider}'")

        try:
            plan = HabitPlanLLMOutput.model_validate(raw_plan)
        except Exception as exc:
            last_validation_errors = str(exc)
            if attempt == MAX_PLAN_RETRIES:
                raise AIPipelineGenerationError(f"LLM JSON did not match expected shape: {exc}") from exc
            continue

        plan = _normalize_llm_output(plan, requested_category=category, user_goal=user_goal, context=context)
        field_errors = _validate_plan_fields(plan)
        if field_errors:
            last_validation_errors = "; ".join(field_errors)
            if attempt < MAX_PLAN_RETRIES and provider == "openai":
                continue
            # On final attempt or mock mode: fall back to mock plan rather than raising
            if provider == "openai":
                raw_plan = _mock_plan_json(user_goal=user_goal, category=category, context=context)
                plan = HabitPlanLLMOutput.model_validate(raw_plan)
                plan = _normalize_llm_output(plan, requested_category=category, user_goal=user_goal, context=context)

        habit_payload = _to_habit_create(plan)
        return GeneratedHabitPlan(
            habit_payload=habit_payload,
            progressions=[step.model_dump() for step in plan.progressions],
            raw_plan=plan.model_dump(),
            provider=provider,
            model=model,
        )

    raise AIPipelineGenerationError("Plan generation failed after maximum retries")


def generate_habit_plan(user_goal: str, category: str, context: Optional[dict] = None) -> GeneratedHabitPlan:
    prompt = _build_prompt(user_goal=user_goal, category=category, context=context)
    return _generate_plan(prompt=prompt, user_goal=user_goal, category=category, context=context)


def _combined_user_idea(recent_messages: Sequence[AIChatMessage], latest_user_message: str) -> str:
    # Reject-aware: only include user messages from AFTER the last rejection
    # response so that off-topic / sensitive / multi-habit history doesn't
    # contaminate the combined idea for a valid follow-up message.
    _REJECTION_PHRASES = (
        "i'm here to help you build habits",   # off_topic
        "healthcare professional",              # sensitive
        "health or medical considerations",     # sensitive
        "one habit to start",                   # multi_habit
        "focus on one habit",                   # multi_habit
    )

    messages = list(recent_messages[-MAX_RECENT_MESSAGES:])

    # Find the last assistant rejection message index
    last_rejection_idx: int = -1
    for i, msg in enumerate(messages):
        if msg.role == "assistant":
            lowered = msg.content.lower()
            if any(phrase in lowered for phrase in _REJECTION_PHRASES):
                last_rejection_idx = i

    # Only consider messages after the last rejection
    relevant = messages[last_rejection_idx + 1:] if last_rejection_idx >= 0 else messages

    parts: List[str] = []
    for message in relevant:
        if message.role != "user":
            continue
        normalized = _normalize_text(message.content)
        if normalized:
            parts.append(normalized)

    latest = _normalize_text(latest_user_message)
    if latest:
        parts.append(latest)

    if not parts:
        return ""

    unique_parts: List[str] = []
    for part in parts:
        if part not in unique_parts:
            unique_parts.append(part)
    return " ".join(unique_parts)


def _has_prior_experience_ask(recent_messages: Sequence[AIChatMessage]) -> bool:
    """Returns True if the assistant has already asked about experience level."""
    experience_ask_phrases = [
        "experience with this",
        "just getting started",
        "tried it before",
        "experience level",
        "beginner or",
        "new to this",
        # phrases from the actual question generated by _needs_idea_clarification
        "worked on something like this",
        "fresh start for you",
        "have you worked",
        "worked on this",
        "done this before",
        "tried this before",
    ]
    return any(
        message.role == "assistant"
        and any(phrase in message.content.lower() for phrase in experience_ask_phrases)
        for message in recent_messages[-6:]
    )


def _has_prior_time_ask(recent_messages: Sequence[AIChatMessage]) -> bool:
    """Returns True if the assistant has already asked about time of day."""
    time_ask_phrases = [
        "time of day",
        "morning or",
        "part of your day",
        "fit into your day",
        "what time",
        "before or after",
    ]
    return any(
        message.role == "assistant"
        and any(phrase in message.content.lower() for phrase in time_ask_phrases)
        for message in recent_messages[-6:]
    )


def _has_prior_obstacle_ask(recent_messages: Sequence[AIChatMessage]) -> bool:
    """Returns True if the assistant has already asked about past obstacles or schedule pressures."""
    obstacle_ask_phrases = [
        "get in the way",
        "gotten in the way",  # past tense form used in the actual question
        "in the way",
        "stopped you",
        "made it hard",
        "biggest challenge",
        "obstacle",
        "busy week",
        "fitting it in",
        "tried to build a habit",
    ]
    return any(
        message.role == "assistant"
        and any(phrase in message.content.lower() for phrase in obstacle_ask_phrases)
        for message in recent_messages[-6:]
    )


def _count_clarification_exchanges(recent_messages: Sequence[AIChatMessage]) -> int:
    """Count how many back-and-forth clarification rounds have occurred."""
    count = 0
    for msg in recent_messages:
        if msg.role == "assistant":
            lowered = msg.content.lower()
            # Detect any clarification question (ends with "?")
            if "?" in lowered:
                count += 1
    return count


def _has_time_of_day_context(idea: str) -> bool:
    lowered = idea.lower()
    return any(token in lowered for token in [
        "morning", "afternoon", "evening", "night", "before bed", "after work",
        "before work", "lunch", "midday", "start my day", "wind down",
    ])


def _has_obstacle_context(idea: str) -> bool:
    lowered = idea.lower()
    return any(token in lowered for token in [
        "struggle", "hard", "difficult", "challenge", "fail", "stop",
        "quit", "busy", "tired", "motivation", "consistent", "consistency",
        "obstacle", "problem", "issue", "barrier", "distract", "anxious",
        "stress", "overwhelm", "forget", "skip", "miss", "can't", "cannot",
        "don't", "never manage", "keep failing", "keep skipping",
    ])


def _needs_idea_clarification(idea: str, recent_messages: Sequence[AIChatMessage]) -> Optional[str]:
    normalized = _normalize_text(idea) or ""
    if not normalized:
        return "Tell me what kind of change you want in your life, what you’re struggling with, and anything that would make the habit realistic or unrealistic for you."

    lowered = normalized.lower()
    vague_markers = {
        "be better",
        "get better",
        "be healthier",
        "improve my life",
        "do better",
        "be more consistent",
    }
    if len(normalized.split()) <= 4 or lowered in vague_markers:
        return "What kind of change are you hoping for day to day, and is there anything that would make the habit realistic or unrealistic for you?"

    # Count prior clarification exchanges — generate after ~3 rounds regardless
    exchange_count = _count_clarification_exchanges(recent_messages)
    if exchange_count >= 3:
        return None

    # Priority queue of missing context (most important first)

    # 1. Experience level — critical for calibrating intensity
    if not _normalize_experience_level(normalized) and not _has_prior_experience_ask(recent_messages):
        return "Have you worked on something like this before, or would this be a fresh start for you?"

    # 2. Time of day — affects habit stickiness
    if not _has_time_of_day_context(normalized) and not _has_prior_time_ask(recent_messages) and exchange_count >= 1:
        return "Is there a part of your day that tends to work better for this — morning, evening, or somewhere in between?"

    # 3. Past obstacles — helps calibrate realism
    if not _has_obstacle_context(normalized) and not _has_prior_obstacle_ask(recent_messages) and exchange_count >= 2:
        return "What’s gotten in the way in the past when you’ve tried to build a habit like this?"

    return None


def _infer_preferred_time_from_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["morning", "before work", "start my day"]):
        return "morning"
    if any(token in lowered for token in ["afternoon", "lunch break", "midday"]):
        return "afternoon"
    if any(token in lowered for token in ["evening", "after work", "night", "before bed", "wind-down", "wind down"]):
        return "evening"
    return "flexible"


def _inferred_experience_from_idea(idea: str) -> str:
    explicit = _normalize_experience_level(idea)
    if explicit:
        return explicit
    lower = idea.lower()
    # Academic / student signals — year in school implies existing study experience
    if any(kw in lower for kw in [
        "third year", "3rd year", "fourth year", "4th year",
        "grad student", "graduate student", "postgrad", "phd", "masters",
        "dissertation", "thesis", "law school", "med school",
        "college senior", "university student", "years of studying",
    ]):
        return "intermediate"
    # "Lock in", "grind", "serious" intent signals without procrastination history
    if any(kw in lower for kw in ["lock in", "serious", "grind", "used to studying", "i study a lot"]):
        return "intermediate"
    return "beginner"


def _proposal_variants(
    category: str,
    idea: str,
    experience_level: str,
    duration_hint: Optional[int],
    schedule_mode_hint: Optional[str],
    times_per_week_hint: Optional[int],
    schedule_days_hint: List[str],
) -> List[Dict[str, Any]]:
    """Produce two plan variants: Balanced (sustainable default) and Ambitious (max for experience level)."""

    # --- Experience-aware defaults and caps ---
    exp = experience_level if experience_level in VALID_EXPERIENCE_LEVELS else "beginner"
    cat = category if category in EXPERIENCE_DURATION_DEFAULTS else "wellness"

    default_duration = EXPERIENCE_DURATION_DEFAULTS[cat][exp]
    default_freq = EXPERIENCE_FREQUENCY_DEFAULTS[cat][exp]
    caps = REALISM_CAPS[cat][exp]

    # Balanced: honor explicitly stated duration even if it exceeds caps —
    # the user knows what they want; caps only gate defaults, not explicit requests.
    bal_duration = duration_hint if duration_hint else default_duration
    bal_freq = times_per_week_hint if (times_per_week_hint and times_per_week_hint <= caps["max_days_per_week"]) else default_freq

    # Ambitious: frequency = balanced + 1 session (capped at max); duration is chosen by GPT via few-shot prompt
    amb_freq = min(bal_freq + 1, caps["max_days_per_week"])

    # --- Resolve schedule mode ---
    base_schedule_mode = schedule_mode_hint
    base_schedule_days = list(schedule_days_hint) if schedule_days_hint else []

    if not base_schedule_mode:
        if cat in {"wellness", "reading", "sleep"}:
            base_schedule_mode = "daily"
        else:
            base_schedule_mode = "times_per_week"
    elif base_schedule_mode == "specific_days" and not base_schedule_days:
        base_schedule_mode = "times_per_week"

    def _days_for_freq(n: int) -> List[str]:
        # Pick evenly-spaced days for a given frequency
        if n >= 7:
            return ORDERED_DAYS.copy()
        step = max(1, 7 // n)
        return ORDERED_DAYS[:n * step:step][:n]

    # Balanced schedule
    if base_schedule_mode == "daily":
        bal_mode, bal_days, bal_tpw = "daily", ORDERED_DAYS.copy(), None
    elif base_schedule_mode == "weekdays":
        bal_mode, bal_days, bal_tpw = "weekdays", ORDERED_DAYS[:5], None
    elif base_schedule_days:
        bal_mode = "specific_days"
        bal_days = base_schedule_days[:bal_freq]
        bal_tpw = None
    else:
        bal_mode = "times_per_week"
        bal_tpw = bal_freq
        bal_days = _days_for_freq(bal_freq)

    # Ambitious schedule — add 1 session; only force daily if already daily or already at daily frequency
    if base_schedule_mode == "daily" or bal_freq >= 7:
        amb_mode, amb_days, amb_tpw = "daily", ORDERED_DAYS.copy(), None
    elif base_schedule_mode == "weekdays":
        # weekdays already 5x; ambitious stays weekdays (adding daily would only add weekends)
        amb_mode, amb_days, amb_tpw = "weekdays", ORDERED_DAYS[:5], None
    else:
        amb_mode = bal_mode
        amb_tpw = amb_freq if amb_mode == "times_per_week" else None
        amb_days = _days_for_freq(amb_freq)

    return [
        {
            "label": "balanced",
            "duration_minutes": bal_duration,
            "schedule_mode": bal_mode,
            "times_per_week": bal_tpw,
            "schedule_days": bal_days,
            "rationale": "A sustainable plan for building the habit consistently without burning out.",
        },
        {
            "label": "ambitious",
            "duration_minutes": None,  # GPT determines this via few-shot prompt
            "balanced_duration": bal_duration,  # passed as context to GPT
            "schedule_mode": amb_mode,
            "times_per_week": amb_tpw,
            "schedule_days": amb_days,
            "rationale": "A step up from the balanced plan — more sessions and more time, calibrated to your experience.",
        },
    ]


def _habit_title_variant(base_title: str, label: str) -> str:
    if label == "ambitious":
        return f"{base_title} (Ambitious)"
    return base_title


def _format_duration(minutes: int) -> str:
    """Return a human-readable duration string: '45 min', '1h', '1h 30m', '3h'."""
    if minutes < 60:
        return f"{minutes} min"
    hours, rem = divmod(minutes, 60)
    return f"{hours}h" if rem == 0 else f"{hours}h {rem}m"


def _schedule_summary_from_payload(habit_payload: HabitCreate) -> str:
    if habit_payload.frequency_type == "daily":
        return "Every day"
    days = _clean_schedule_days((habit_payload.frequency_pattern or {}).get("days"))
    if not days:
        return "Custom schedule"
    if days == ORDERED_DAYS:
        return "Every day"
    if days == ORDERED_DAYS[:5]:
        return "Weekdays"
    if days == ORDERED_DAYS[5:]:
        return "Weekends"
    return ", ".join(day.title() for day in days)


def _candidate_from_generated_plan(plan: GeneratedHabitPlan, duration_minutes: int, rationale: str, label: str) -> AIHabitCandidate:
    habit_payload = plan.habit_payload.model_copy(deep=True)
    habit_payload.name = _habit_title_variant(habit_payload.name, label)
    return AIHabitCandidate(
        title=habit_payload.name,
        category=habit_payload.category,
        description=habit_payload.description,
        suggested_schedule=_schedule_summary_from_payload(habit_payload),
        duration_minutes=duration_minutes,
        rationale=rationale,
        variant=label,
        habit_payload=habit_payload,
        progressions=plan.progressions,
    )


def _what_i_heard_summary(idea: str) -> str:
    summary = _summarize_goal(idea)
    return f"You want a realistic habit built around: {summary}"


def propose_habit_candidates(
    recent_messages: Sequence[AIChatMessage],
    latest_user_message: str,
) -> HabitProposalResult:
    provider, model = _provider_and_model()

    # 1. Cap context window — never process more than MAX_RECENT_MESSAGES
    capped_messages = list(recent_messages[-MAX_RECENT_MESSAGES:])

    combined_idea = _combined_user_idea(capped_messages, latest_user_message)

    # 2. Intent classification — short-circuit before doing any LLM work
    intent = classify_intent(latest_user_message, capped_messages)
    if intent == "off_topic":
        return HabitProposalResult(
            action="off_topic",
            provider=provider,
            model=model,
            assistant_message="I'm here to help you build habits. What kind of change do you want to make in your daily routine?",
            what_i_heard=None,
            candidates=[],
            needs_clarification=True,
        )
    if intent == "sensitive":
        return HabitProposalResult(
            action="sensitive",
            provider=provider,
            model=model,
            assistant_message=(
                "It sounds like there may be some health or medical considerations here. "
                "I'd recommend checking in with a healthcare professional first — "
                "once you have that guidance, I'm happy to help you build a habit around it."
            ),
            what_i_heard=None,
            candidates=[],
            needs_clarification=True,
        )
    if intent == "multi_habit":
        return HabitProposalResult(
            action="multi_habit",
            provider=provider,
            model=model,
            assistant_message=(
                "Building several habits at once makes it harder for any of them to stick. "
                "Let's focus on one habit to start — which one matters most to you right now?"
            ),
            what_i_heard=None,
            candidates=[],
            needs_clarification=True,
        )

    # 3. Clarification check (vague input, missing experience level)
    clarification = _needs_idea_clarification(combined_idea, capped_messages)
    if clarification:
        return HabitProposalResult(
            action="clarify",
            provider=provider,
            model=model,
            assistant_message=clarification,
            what_i_heard=_what_i_heard_summary(combined_idea) if combined_idea else None,
            candidates=[],
            needs_clarification=True,
        )

    inferred_category, confident_category = _infer_category_from_text(combined_idea)
    category = inferred_category or "wellness"
    if not confident_category and not inferred_category:
        category = "wellness"

    duration_hint = _duration_minutes_from_text(combined_idea)
    schedule_mode_hint = _normalize_schedule_mode(combined_idea)
    times_per_week_hint = _count_per_week_from_text(combined_idea)
    schedule_days_hint = _schedule_days_from_text(combined_idea)
    experience_level = _inferred_experience_from_idea(combined_idea)
    preferred_time = _infer_preferred_time_from_text(combined_idea)

    # 4. Apply REALISM_CAPS — clamp schedule hints but NOT duration.
    # Duration is intentionally left alone: the user explicitly stated it and we should honour it.
    # caps still gate the default used when duration_hint is absent (handled in _proposal_variants).
    if experience_level in VALID_EXPERIENCE_LEVELS and category in REALISM_CAPS:
        caps = REALISM_CAPS[category][experience_level]
        if times_per_week_hint and times_per_week_hint > caps["max_days_per_week"]:
            times_per_week_hint = caps["max_days_per_week"]
        if schedule_days_hint and len(schedule_days_hint) > caps["max_days_per_week"]:
            schedule_days_hint = schedule_days_hint[: caps["max_days_per_week"]]

    candidates: List[AIHabitCandidate] = []
    balanced_duration_generated: Optional[int] = None  # track for ambitious context
    balanced_days_generated: Optional[List[str]] = None  # track for ambitious context

    for variant in _proposal_variants(
        category=category,
        idea=combined_idea,
        experience_level=experience_level,
        duration_hint=duration_hint,
        schedule_mode_hint=schedule_mode_hint,
        times_per_week_hint=times_per_week_hint,
        schedule_days_hint=schedule_days_hint,
    ):
        is_ambitious = variant["label"] == "ambitious"

        # For ambitious: duration is None — GPT will choose it via few-shot prompt
        # For balanced: use the pre-computed duration
        context_duration = variant["duration_minutes"]  # None for ambitious

        context = {
            "experience_level": experience_level,
            "available_time": context_duration or (balanced_duration_generated or variant.get("balanced_duration")),
            "preferred_time": preferred_time,
            "habit_description": _normalize_text(combined_idea),
            "schedule_mode": variant["schedule_mode"],
            "times_per_week": variant["times_per_week"],
            "schedule_days": variant["schedule_days"],
            "schedule_text": _derived_schedule_text(
                variant["schedule_mode"],
                variant["times_per_week"],
                variant["schedule_days"],
            ),
            "duration_minutes": context_duration,
            # Ambitious-specific: tell GPT which variant this is and the balanced baseline
            "variant": variant["label"],
            "balanced_duration": balanced_duration_generated or variant.get("balanced_duration"),
            "balanced_days": balanced_days_generated if is_ambitious else variant["schedule_days"],
        }

        generated = generate_habit_plan(
            user_goal=combined_idea,
            category=category,
            context=context,
        )

        # For ambitious: use GPT's chosen duration if it output one; cap at REALISM_CAPS
        if is_ambitious:
            gpg_duration = generated.raw_plan.get("duration_minutes")
            if gpg_duration and isinstance(gpg_duration, int) and gpg_duration > 0:
                # Respect REALISM_CAPS upper bound
                max_dur = caps["max_duration_minutes"] if experience_level in VALID_EXPERIENCE_LEVELS and category in REALISM_CAPS else 120
                actual_duration = min(gpg_duration, max_dur)
            else:
                # Fallback: balanced + a modest category-aware increment
                base = balanced_duration_generated or variant.get("balanced_duration") or 20
                fallback_increment = 10 if category in {"wellness", "reading", "sleep"} else 15
                actual_duration = min(base + fallback_increment, caps["max_duration_minutes"])
        else:
            actual_duration = variant["duration_minutes"]
            balanced_duration_generated = actual_duration  # save for ambitious context
            balanced_days_generated = list(variant["schedule_days"])  # save for ambitious context

        candidates.append(
            _candidate_from_generated_plan(
                generated,
                duration_minutes=actual_duration,
                rationale=variant["rationale"],
                label=variant["label"],
            )
        )

    return HabitProposalResult(
        action="propose",
        provider=provider,
        model=model,
        assistant_message="Here are a few habit options I think fit what you described. Pick one to use as-is, or refine one if you want it adjusted.",
        what_i_heard=_what_i_heard_summary(combined_idea),
        candidates=candidates,
        needs_clarification=False,
    )


def _candidate_schedule_context(candidate: AIHabitCandidate) -> Dict[str, Any]:
    habit_payload = candidate.habit_payload
    schedule_days = _clean_schedule_days((habit_payload.frequency_pattern or {}).get("days"))
    if habit_payload.frequency_type == "daily":
        schedule_mode = "daily"
        schedule_days = ORDERED_DAYS.copy()
        times_per_week = None
    elif schedule_days == ORDERED_DAYS[:5]:
        schedule_mode = "weekdays"
        times_per_week = None
    elif schedule_days == ORDERED_DAYS[5:]:
        schedule_mode = "weekends"
        times_per_week = None
    elif schedule_days:
        schedule_mode = "specific_days"
        times_per_week = len(schedule_days)
    else:
        schedule_mode = "daily"
        times_per_week = None

    return {
        "schedule_mode": schedule_mode,
        "times_per_week": times_per_week,
        "schedule_days": schedule_days,
        "schedule_text": _derived_schedule_text(schedule_mode, times_per_week, schedule_days),
    }


def _apply_refinement_to_context(base_context: Dict[str, Any], refinement: str) -> Dict[str, Any]:
    updated = dict(base_context)
    lowered = refinement.lower()

    explicit_schedule_mode = _normalize_schedule_mode(refinement)
    explicit_times = _count_per_week_from_text(refinement)
    explicit_days = _schedule_days_from_text(refinement)
    explicit_duration = _duration_minutes_from_text(refinement)
    explicit_preferred_time = _infer_preferred_time_from_text(refinement)

    if explicit_schedule_mode:
        updated["schedule_mode"] = explicit_schedule_mode
    if explicit_times:
        updated["times_per_week"] = explicit_times
    if explicit_days:
        updated["schedule_days"] = explicit_days

    if explicit_duration:
        updated["duration_minutes"] = explicit_duration
        updated["available_time"] = explicit_duration

    if explicit_preferred_time != "flexible":
        updated["preferred_time"] = explicit_preferred_time

    if "easier" in lowered:
        current_duration = _duration_minutes_from_text(updated.get("duration_minutes")) or 15
        updated["duration_minutes"] = max(5, current_duration - 5)
        updated["available_time"] = updated["duration_minutes"]
    elif "more realistic" in lowered:
        current_duration = _duration_minutes_from_text(updated.get("duration_minutes")) or 15
        updated["duration_minutes"] = max(10, min(current_duration, 20))
        updated["available_time"] = updated["duration_minutes"]

    schedule_mode = _normalize_schedule_mode(updated.get("schedule_mode"))
    schedule_days = _clean_schedule_days(updated.get("schedule_days"))
    times_per_week = _count_per_week_from_text(updated.get("times_per_week"))

    if schedule_mode == "daily":
        schedule_days = ORDERED_DAYS.copy()
        times_per_week = None
    elif schedule_mode == "weekdays":
        schedule_days = ORDERED_DAYS[:5]
        times_per_week = None
    elif schedule_mode == "weekends":
        schedule_days = ORDERED_DAYS[5:]
        times_per_week = None
    elif schedule_mode == "times_per_week" and not times_per_week:
        times_per_week = len(schedule_days) if schedule_days else 3

    updated["schedule_mode"] = schedule_mode
    updated["times_per_week"] = times_per_week
    updated["schedule_days"] = schedule_days
    updated["schedule_text"] = _derived_schedule_text(schedule_mode, times_per_week, schedule_days)
    return updated


def refine_habit_candidate(
    idea: str,
    selected_candidate: AIHabitCandidate,
    refinement: str,
    recent_messages: Sequence[AIChatMessage],
) -> CandidateRefinementResult:
    _ = recent_messages
    base_context = {
        "experience_level": "beginner",
        "available_time": selected_candidate.duration_minutes,
        "preferred_time": _infer_preferred_time_from_text(" ".join([idea, refinement])),
        "habit_description": selected_candidate.description,
        "duration_minutes": selected_candidate.duration_minutes,
        "critique": refinement,
        "current_plan": {
            "habit_name": selected_candidate.title,
            "description": selected_candidate.description,
            "suggested_schedule": selected_candidate.suggested_schedule,
        },
    }
    base_context.update(_candidate_schedule_context(selected_candidate))
    updated_context = _apply_refinement_to_context(base_context, refinement)

    generated = generate_habit_plan(
        user_goal=idea,
        category=selected_candidate.category,
        context=updated_context,
    )
    refined_candidate = _candidate_from_generated_plan(
        generated,
        duration_minutes=updated_context["duration_minutes"],
        rationale="This version adjusts the habit around your feedback while keeping it realistic.",
        label="balanced",
    )
    return CandidateRefinementResult(
        provider=generated.provider,
        model=generated.model,
        assistant_message="I adjusted that option. See if this version feels closer to what you want.",
        candidate=refined_candidate,
    )


def create_habit_from_candidate(candidate: AIHabitCandidate) -> GeneratedHabitPlan:
    provider, model = _provider_and_model()
    return GeneratedHabitPlan(
        habit_payload=candidate.habit_payload,
        progressions=candidate.progressions,
        raw_plan={
            "habit_name": candidate.title,
            "category": candidate.category,
            "description": candidate.description,
            "suggested_schedule": candidate.suggested_schedule,
            "duration_minutes": candidate.duration_minutes,
            "rationale": candidate.rationale,
        },
        provider=provider,
        model=model,
    )


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
        "schedule_mode": draft.schedule_mode,
        "times_per_week": draft.times_per_week,
        "schedule_text": draft.schedule_text,
        "schedule_days": draft.schedule_days,
        "duration_minutes": draft.duration_minutes,
        "habit_type": draft.habit_type or "binary",
    }
    if draft.motivation_statement:
        context["user_motivation"] = draft.motivation_statement
    if draft.target_value is not None:
        context["target_value"] = draft.target_value
        context["quantity_unit"] = draft.quantity_unit
    if critique:
        context["critique"] = critique
    if current_plan:
        context["current_plan"] = current_plan.model_dump()
    return context


def _validated_draft(draft: AIIntakeDraft) -> AIIntakeDraft:
    normalized_goal = _normalize_text(draft.goal_summary)
    normalized_description = _normalize_text(draft.habit_description)
    explicit_frequency = _canonical_frequency(draft.frequency)
    normalized_schedule_mode = _normalize_schedule_mode(draft.schedule_mode)
    normalized_times_per_week = _count_per_week_from_text(draft.times_per_week)
    normalized_schedule_days = _clean_schedule_days(draft.schedule_days)
    normalized_schedule_text = _schedule_text_from_value(draft.schedule_text)
    if not normalized_schedule_mode:
        normalized_schedule_mode = _normalize_schedule_mode(normalized_schedule_text) or _normalize_schedule_mode(explicit_frequency)
    if not normalized_times_per_week:
        normalized_times_per_week = _count_per_week_from_text(normalized_schedule_text) or _count_per_week_from_text(explicit_frequency)
    if not normalized_schedule_days and normalized_schedule_text:
        normalized_schedule_days = _schedule_days_from_text(normalized_schedule_text)
    if not normalized_schedule_days and explicit_frequency:
        normalized_schedule_days = _schedule_days_from_text(explicit_frequency)
    if not normalized_schedule_mode and normalized_schedule_days:
        normalized_schedule_mode = "specific_days"
    if normalized_schedule_mode in {"daily", "weekdays", "weekends"} and not normalized_schedule_days:
        normalized_schedule_days = _canonical_days_for_mode(normalized_schedule_mode)
    if not normalized_schedule_text:
        normalized_schedule_text = _derived_schedule_text(normalized_schedule_mode, normalized_times_per_week, normalized_schedule_days)
    normalized_frequency = _derived_frequency(normalized_schedule_mode, normalized_times_per_week, normalized_schedule_days) or explicit_frequency

    normalized = AIIntakeDraft(
        goal_summary=normalized_goal,
        habit_description=normalized_description,
        frequency=normalized_frequency,
        schedule_mode=normalized_schedule_mode,
        times_per_week=normalized_times_per_week,
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
    if not normalized.category:
        missing.append("category")
    if not normalized.experience_level:
        missing.append("experience_level")
    if not normalized.duration_minutes:
        missing.append("duration_minutes")
    if not normalized.schedule_mode:
        missing.append("schedule_mode")
    if normalized.schedule_mode == "times_per_week" and not normalized.times_per_week:
        missing.append("times_per_week")
    if normalized.schedule_mode in {"specific_days", "times_per_week"} and not normalized.schedule_days:
        missing.append("schedule_days")
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
        "schedule_mode": _normalize_schedule_mode(message),
        "times_per_week": _count_per_week_from_text(message),
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
  "schedule_mode": "daily|weekdays|weekends|specific_days|times_per_week|null",
  "times_per_week": 3 or null,
  "schedule_text": "string or null",
  "schedule_days": ["monday"] or [],
  "duration_minutes": 20 or null,
  "experience_level": "beginner|intermediate|advanced|null",
  "category": "fitness|study|wellness|reading|sleep|null",
  "category_confidence": "low|medium|high",
  "motivation_statement": "string or null",
  "habit_type": "binary|tracked|null",
  "target_value": 5.0 or null,
  "quantity_unit": "km|pages|minutes|reps|glasses|null"
}}

Rules:
- Only extract fields the user actually implied.
- If category is only weakly implied, leave category null or confidence low.
- Experience level must map to beginner, intermediate, advanced, or null.
- Frequency should stay as a plain-language phrase if present.
- schedule_mode should be one of daily, weekdays, weekends, specific_days, times_per_week when the user clearly implied one.
- times_per_week should only be set when the user clearly gave a weekly count.
- schedule_days must only include concrete weekdays the user actually specified or strongly implied.
- If the user only said a count like "3 times a week" without days, leave schedule_days empty.
- duration_minutes should be an integer minute count when the user gave one.
- motivation_statement: extract the user's stated reason or "why" if expressed (e.g. "to lose weight", "because I want to feel healthier"). Never fabricate — leave null if not stated.
- habit_type: set "tracked" if the user mentioned a measurable target (e.g. "run 5km", "drink 8 glasses", "read 30 pages"); "binary" for checkbox habits (meditate, stretch, journal). Leave null if unclear.
- target_value + quantity_unit: only set when habit_type is "tracked" and the user gave a concrete amount.
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
    schedule_mode = _normalize_schedule_mode(extracted.schedule_mode) or current_draft.schedule_mode
    times_per_week = _count_per_week_from_text(extracted.times_per_week) or current_draft.times_per_week
    schedule_days = _clean_schedule_days(extracted.schedule_days) or current_draft.schedule_days
    schedule_text = _schedule_text_from_value(extracted.schedule_text) or current_draft.schedule_text
    if not schedule_mode:
        schedule_mode = _normalize_schedule_mode(frequency) or _normalize_schedule_mode(schedule_text)
    if not times_per_week:
        times_per_week = _count_per_week_from_text(frequency) or _count_per_week_from_text(schedule_text)
    if not schedule_days and schedule_text:
        schedule_days = _schedule_days_from_text(schedule_text)
    if not schedule_days and frequency:
        schedule_days = _schedule_days_from_text(frequency)
    if not schedule_days and schedule_mode in {"daily", "weekdays", "weekends"}:
        schedule_days = _canonical_days_for_mode(schedule_mode)
    if not schedule_mode and schedule_days:
        schedule_mode = "specific_days"
    if not schedule_text:
        schedule_text = _derived_schedule_text(schedule_mode, times_per_week, schedule_days)
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
            schedule_mode=schedule_mode,
            times_per_week=times_per_week,
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
    if field == "schedule_mode":
        return "What schedule fits best: every day, weekdays, weekends, specific days, or a certain number of times per week?"
    if field == "times_per_week":
        return "How many times per week do you want to do it?"
    if field == "schedule_days":
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
    # 1. Cap context window — never process more than MAX_RECENT_MESSAGES
    capped_messages = list(recent_messages[-MAX_RECENT_MESSAGES:])

    # 2. Classify intent of the latest message
    intent = classify_intent(latest_user_message, capped_messages)

    base_draft = _validated_draft(current_draft or AIIntakeDraft())

    # 3. Handle intents that bypass normal intake flow
    if intent == "off_topic":
        return IntakeStepResult(
            assistant_message=(
                "I’m here to help you build habits! Let’s get back on track. "
                "What habit are you thinking of working on?"
            ),
            updated_draft=base_draft,
            missing_fields=missing_fields_for_draft(base_draft),
            conflict_fields=[],
            ready_for_confirmation=False,
            confirmation_summary=None,
            needs_clarification=False,
            needs_correction=False,
            intent=intent,
        )

    if intent == "sensitive":
        return IntakeStepResult(
            assistant_message=(
                "It sounds like you may be dealing with something that deserves proper support. "
                "I’d recommend speaking with a doctor or therapist for personalized guidance. "
                "I’m best suited for everyday habit-building — let me know if there’s a "
                "different habit you’d like to explore."
            ),
            updated_draft=base_draft,
            missing_fields=missing_fields_for_draft(base_draft),
            conflict_fields=[],
            ready_for_confirmation=False,
            confirmation_summary=None,
            needs_clarification=False,
            needs_correction=False,
            intent=intent,
        )

    if intent == "multi_habit":
        return IntakeStepResult(
            assistant_message=(
                "It sounds like you have a few habits in mind — that’s great! "
                "Let’s focus on one to start so we can build a solid plan. "
                "Which one matters most to you right now?"
            ),
            updated_draft=base_draft,
            missing_fields=missing_fields_for_draft(base_draft),
            conflict_fields=[],
            ready_for_confirmation=False,
            confirmation_summary=None,
            needs_clarification=False,
            needs_correction=False,
            intent=intent,
        )

    # 4. Normal intake flow
    extraction = _extract_intake_update(
        recent_messages=capped_messages,
        current_draft=base_draft,
        latest_user_message=latest_user_message,
    )
    updated_draft = _merged_draft(base_draft, extraction=extraction, latest_user_message=latest_user_message)

    # 5. Infer frequency/duration defaults from experience + category when fields are missing
    updated_draft = _infer_defaults_from_experience(updated_draft)

    # 6. Realism check
    realism_result = check_realism(updated_draft)

    conflict_fields, conflict_message = _first_conflict(updated_draft)
    missing_fields = missing_fields_for_draft(updated_draft)
    ready_for_confirmation = not missing_fields and not conflict_fields
    confirmation_summary = _confirmation_summary(updated_draft) if ready_for_confirmation else None

    required_field_changed = any(
        getattr(base_draft, field) != getattr(updated_draft, field)
        for field in [
            "goal_summary",
            "frequency",
            "schedule_mode",
            "times_per_week",
            "schedule_text",
            "schedule_days",
            "duration_minutes",
            "experience_level",
            "category",
        ]
    )
    needs_correction = bool(conflict_fields)
    needs_clarification = bool(latest_user_message.strip()) and not required_field_changed and not ready_for_confirmation and not needs_correction

    # 7. Build assistant message
    if ready_for_confirmation:
        base_message = f"{confirmation_summary}\n\nIf that looks right, confirm and I’ll generate your plan."
    elif needs_correction and conflict_message:
        base_message = conflict_message
    elif needs_clarification:
        base_message = f"I still need one more detail. {_next_question(missing_fields)}"
    else:
        base_message = _next_question(missing_fields)

    # Prepend realism warning when applicable
    if not realism_result.is_realistic:
        assistant_message = f"{realism_result.warning_message}\n\n{base_message}"
    else:
        assistant_message = base_message

    return IntakeStepResult(
        assistant_message=assistant_message,
        updated_draft=updated_draft,
        missing_fields=missing_fields,
        conflict_fields=conflict_fields,
        ready_for_confirmation=ready_for_confirmation,
        confirmation_summary=confirmation_summary,
        needs_clarification=needs_clarification,
        needs_correction=needs_correction,
        intent=intent,
        realism_warning=realism_result.warning_message if not realism_result.is_realistic else None,
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
        for field in [
            "goal_summary",
            "frequency",
            "schedule_mode",
            "times_per_week",
            "schedule_text",
            "schedule_days",
            "duration_minutes",
            "experience_level",
            "category",
        ]
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


# =============================================================================
# TWO-TIER CHAT ARCHITECTURE
# =============================================================================

# Fields required before Tier 2 fires (confidence gate).
_CONFIDENCE_FIELDS: List[tuple] = [
    # (field_name, weight)  — weights sum to 1.0
    ("goal_summary", 0.25),
    ("category", 0.20),
    ("frequency", 0.20),
    ("duration_minutes", 0.15),
    ("experience_level", 0.10),
    ("schedule_days", 0.10),  # non-empty list counts as present
]
_CONFIDENCE_THRESHOLD = 0.80

# Cheap pre-filter keyword sets (no API call).
_OFFTOPIC_KEYWORDS = {
    "weather", "stock", "crypto", "bitcoin", "ethereum", "politics",
    "election", "movie", "film", "music", "song", "recipe", "cook",
    "dating", "relationship", "sports score", "football", "soccer",
    "basketball", "baseball", "nba", "nfl", "mlb",
}
_HABIT_KEYWORDS = {
    "habit", "routine", "goal", "workout", "exercise", "study", "sleep",
    "read", "meditate", "run", "walk", "practice", "train", "gym",
    "journal", "drink water", "stretch", "yoga", "wake up", "morning",
    "evening", "daily", "weekly", "schedule", "remind",
}


def _compute_confidence(draft: AIIntakeDraft) -> float:
    """Rule-based confidence from field coverage. Pure Python — no AI involved.

    Tracked/cumulative habits (water, steps, etc.) never get duration_minutes or
    experience_level, so those slots are filled differently:
      - duration_minutes: satisfied by target_value for tracked habits
      - experience_level: not required for tracked habits — awarded automatically
    """
    is_tracked = draft.habit_type == "tracked"
    score = 0.0
    for field, weight in _CONFIDENCE_FIELDS:
        if field == "schedule_days":
            if getattr(draft, field, None):
                score += weight
        elif field == "duration_minutes":
            # For tracked habits target_value serves this role
            if draft.duration_minutes is not None or (
                is_tracked and draft.target_value is not None
            ):
                score += weight
        elif field == "experience_level":
            # Irrelevant for tracked habits — don't penalise for not having it
            if is_tracked or getattr(draft, field, None) is not None:
                score += weight
        else:
            if getattr(draft, field, None) is not None:
                score += weight
    return round(score, 3)


def _is_clearly_offtopic(message: str) -> bool:
    """Cheap keyword check. Returns True only when confidently off-topic."""
    lower = message.lower()
    # If the message mentions any habit-related term, it's probably in-scope.
    if any(kw in lower for kw in _HABIT_KEYWORDS):
        return False
    return any(kw in lower for kw in _OFFTOPIC_KEYWORDS)


_TIER1_SYSTEM_PROMPT = """\
You are HabitFlow's habit coach. Your job is to gather what you need to build a \
personalized habit plan through natural, fluid conversation — one question at a time.

You extract structured fields from what the user says and decide whether to:
- ask a clarifying question (action: "clarify")
- answer a general habit-domain question and pivot back to creation (action: "advise")
- politely redirect if clearly out-of-scope (action: "redirect")

━━━ TWO HABIT TYPES — behave differently for each ━━━

SESSION habits (fitness, study, reading, timed wellness like meditation/yoga):
  The user does a discrete block of activity. Fields needed: duration_minutes, schedule_days, trigger_value.

CUMULATIVE DAILY habits (water intake, steps, pages read as a count, calories, etc.):
  The user accumulates toward a daily target throughout the day — there is no single "session."
  Fields needed: target_value + quantity_unit, schedule_days, trigger_value (reminder time).
  DO NOT ask duration_minutes for cumulative habits — it does not apply.
  DO NOT ask target_value/quantity_unit more than once. Once the user states their goal
  (e.g. "2 liters", "8 glasses", "10,000 steps"), set target_value + quantity_unit and
  never ask about the quantity in any other phrasing.

Detect cumulative habits from words like: "drink", "water", "liters", "glasses", "steps",
"walk X steps", "calories", "pages per day", "words per day".

━━━ FIELD INFERENCE POLICY ━━━

INFER SILENTLY — extract from context, never ask:
- goal_summary: one-sentence description of what they want to do
- category: fitness | study | wellness | reading | sleep — infer from their description
- frequency: daily | weekly | specific_days
    * Cumulative daily habits (water, steps) → always "daily"
    * Beginner runner → specific_days (3x/week)
    * Intermediate runner → specific_days (4-5x/week)
    * Meditation/journaling → daily
  Set frequency in extracted{}; confirm with the user only for non-daily habits.
- motivation_statement: passively extract the user's "why" if mentioned
- habit_type: "binary" by default; "tracked" if they mention a measurable quantity
- target_value + quantity_unit: extract immediately when the user states a quantity.
  Do not ask again once set.

ASK IF NOT CLEARLY INFERABLE:
- experience_level: beginner | intermediate | advanced
    * Infer only when explicit: "third year student", "grad student", "phd", "masters",
      "law school", "med school", "college senior", "just starting", "never done this",
      "i've been doing this for years", "serious about it", "i study a lot"
    * Skip entirely for cumulative habits (experience level is irrelevant for drinking water).
    * If ambiguous for session habits, ask: "Are you new to [habit] or have you done it before?"

ALWAYS ASK — never infer or assume:
- schedule_days: always ask which specific days, even if frequency is inferred.
    * For daily habits ask: "Which days of the week — every day, or do you take any days off?"
    * For session habits, present a frequency suggestion: "For a beginner runner, 3 days a \
      week is a solid start — which days work best for you?"
- duration_minutes: ask only for SESSION habits if not stated. Skip for cumulative habits.
    Honor the user's stated duration exactly — no adjustment.
- trigger_value (reminder time): always ask what time works for them.
    For cumulative habits, frame it as a reminder: "Would you like a reminder time to \
    help you stay on track — like a morning nudge or an afternoon check-in?"
    Never assume a time.

━━━ CONVERSATION RULES ━━━
- Ask ONE question at a time. Never list multiple questions.
- NEVER re-ask a field that is already set in current_draft. Check current_draft before \
  every question. If target_value is set, do not ask about quantity in any form.
- Keep language natural and habit-appropriate. Don't ask "how long do you want to dedicate \
  to this habit" for something like drinking water or hitting a step count.
- Priority for session habits:  goal_summary → category → experience_level (if needed) \
  → duration_minutes → frequency + schedule_days → trigger_value
- Priority for cumulative habits: goal_summary → category → target_value + quantity_unit \
  → schedule_days → trigger_value
- Once all required fields are gathered, wrap up warmly. Do NOT generate the plan yourself.

━━━ EXTRACTION RULES — put every recognised value in extracted{} immediately ━━━

When the user mentions a quantity (e.g. "2 liters", "8 glasses", "10,000 steps"):
  extracted must include ALL THREE: habit_type, target_value, quantity_unit
  e.g. {"habit_type": "tracked", "target_value": 2.0, "quantity_unit": "liters"}

When the user mentions specific days or a schedule:
  extracted must include schedule_days as a list of lowercase day names
  "every day except Sundays" → {"schedule_days": ["monday","tuesday","wednesday","thursday","friday","saturday"]}
  "weekdays" → {"schedule_days": ["monday","tuesday","wednesday","thursday","friday"]}

When the user mentions a specific time (e.g. "8am", "8:00 am", "6:30 in the morning"):
  extracted must include trigger_value in 24-hour HH:MM format
  "8:00 am" → {"trigger_value": "08:00"}
  "6:30 in the morning" → {"trigger_value": "06:30"}
  Also extract preferred_time: "morning" | "afternoon" | "evening"

Never leave extracted{} empty when the user's message contains any of the above.
If nothing new was said, extracted{} may be omitted or {}.

RESPONSE FORMAT — always return valid JSON:
{
  "action": "clarify" | "advise" | "redirect",
  "assistant_message": "...",
  "extracted": {
    // every field recognised this turn — do not omit fields the user just stated
  }
}
"""


def _tier1_call(
    message: str,
    draft: AIIntakeDraft,
    recent_messages: List[AIChatMessage],
    model: str,
) -> dict:
    """Tier 1: extract fields + determine intent. Returns raw JSON dict."""
    draft_dict = {k: v for k, v in draft.model_dump().items() if v is not None and v != [] and v != "flexible" and v != 15}

    messages: List[Dict[str, str]] = [{"role": "system", "content": _TIER1_SYSTEM_PROMPT}]

    # Include recent context (capped)
    for m in recent_messages[-MAX_RECENT_MESSAGES:]:
        messages.append({"role": m.role, "content": m.content})

    user_payload = {
        "user_message": message,
        "current_draft": draft_dict,
    }
    messages.append({"role": "user", "content": json.dumps(user_payload)})

    return _call_openai_messages_for_json(messages, model)


_TIER2_SYSTEM_PROMPT = """\
You are HabitFlow's habit planner. Given a complete habit intake draft, generate \
exactly two habit variants: "balanced" (sustainable) and "ambitious" (challenging).

RULES
- Honor duration_minutes exactly as given — do NOT reduce or cap it.
- Use category, frequency, schedule_days, experience_level to shape each plan.
- Each variant must have a distinct duration_minutes and/or schedule that reflects \
  the balanced vs ambitious difference.
- progression: 4 weeks, each week slightly increasing challenge.
- trigger_type: always "time"; trigger_value: "HH:MM" 24-hour format.
  If the draft contains trigger_value, use it exactly.
  Otherwise fall back to preferred_time (morning→07:00, afternoon→14:00, evening→20:00, flexible→07:00).
- frequency_type: always "daily" (for daily/weekdays/weekends) or "specific_days" (for named days).
- frequency_pattern: ALWAYS a dict with a "days" key — never null.
  daily → {"days": ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]}
  specific_days → {"days": ["monday","wednesday","friday"]} (use the draft's schedule_days)

RESPONSE FORMAT — valid JSON only:
{
  "candidates": [
    {
      "title": "...",
      "category": "fitness|study|wellness|reading|sleep",
      "description": "...",
      "suggested_schedule": "...",
      "duration_minutes": 60,
      "rationale": "...",
      "variant": "balanced",
      "habit_payload": {
        "name": "...",
        "category": "...",
        "description": "...",
        "trigger_type": "time",
        "trigger_value": "07:00",
        "frequency_type": "daily",
        "frequency_pattern": {"days": ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]},
        "requires_quantity": false,
        "quantity_unit": null,
        "allows_notes": true,
        "motivation_statement": null
      },
      "progressions": [
        {"week": 1, "description": "..."},
        {"week": 2, "description": "..."},
        {"week": 3, "description": "..."},
        {"week": 4, "description": "..."}
      ]
    },
    { "variant": "ambitious", ... }
  ],
  "summary_message": "Here are two plans I put together for you:"
}
"""


def _tier2_call(draft: AIIntakeDraft, model: str) -> dict:
    """Tier 2: generate both variants from a confident draft. Returns raw JSON dict."""
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _TIER2_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(draft.model_dump())},
    ]
    return _call_openai_messages_for_json(messages, model)


_DAY_ALIASES: Dict[str, str] = {
    "mon": "monday", "tue": "tuesday", "tues": "tuesday",
    "wed": "wednesday", "thu": "thursday", "thur": "thursday", "thurs": "thursday",
    "fri": "friday", "sat": "saturday", "sun": "sunday",
}


def _coerce_schedule_days(value: object) -> List[str]:
    """Normalize schedule_days to a list of lowercase day names regardless of AI format.

    Handles:
      - Already a list: ["Monday", "Wednesday"] → ["monday", "wednesday"]
      - Comma/slash separated string: "Mon, Wed, Fri" → ["monday", "wednesday", "friday"]
      - Range string: "Monday through Saturday" → ["monday"..."saturday"]
      - Plain prose: "weekdays" → ["monday","tuesday","wednesday","thursday","friday"]
    """
    if isinstance(value, list):
        result = []
        for item in value:
            day = str(item).strip().lower()
            day = _DAY_ALIASES.get(day, day)
            if day in VALID_DAYS:
                result.append(day)
        return result

    if not isinstance(value, str):
        return []

    lower = value.strip().lower()

    # Shorthand expansions
    if lower in ("weekdays", "weekday", "mon-fri", "mon–fri"):
        return ["monday", "tuesday", "wednesday", "thursday", "friday"]
    if lower in ("weekends", "weekend", "sat-sun", "sat/sun"):
        return ["saturday", "sunday"]
    if lower in ("daily", "every day", "all week", "all days"):
        return list(ORDERED_DAYS)

    # "X through Y" / "X to Y" range
    for sep in (" through ", " to ", "-", "–"):
        if sep in lower:
            parts = lower.split(sep, 1)
            start = parts[0].strip()
            end = parts[1].strip()
            start = _DAY_ALIASES.get(start, start)
            end = _DAY_ALIASES.get(end, end)
            if start in ORDERED_DAYS and end in ORDERED_DAYS:
                si, ei = ORDERED_DAYS.index(start), ORDERED_DAYS.index(end)
                if si <= ei:
                    return ORDERED_DAYS[si: ei + 1]

    # Comma / slash / space separated list
    import re as _re
    tokens = _re.split(r"[,/\s]+", lower)
    result = []
    for token in tokens:
        token = token.strip().rstrip(".")
        token = _DAY_ALIASES.get(token, token)
        if token in VALID_DAYS:
            result.append(token)
    return result


def _merge_extracted(draft: AIIntakeDraft, extracted: dict) -> AIIntakeDraft:
    """Merge fields extracted by Tier 1 into the current draft."""
    data = draft.model_dump()
    allowed = {
        "goal_summary", "habit_description", "frequency", "schedule_mode",
        "schedule_days", "duration_minutes", "experience_level", "category",
        "preferred_time", "available_time", "motivation_statement",
        "habit_type", "target_value", "quantity_unit", "trigger_value",
    }
    for key, val in extracted.items():
        if key not in allowed or val is None:
            continue
        if key == "schedule_days":
            coerced = _coerce_schedule_days(val)
            if coerced:  # only update if we got something valid
                data[key] = coerced
        else:
            data[key] = val
    return AIIntakeDraft(**data)


def _parse_candidates(raw_candidates: List[dict]) -> List:
    """Parse Tier 2 candidate dicts into AIChatCandidate models (imported lazily)."""
    from ..models import AIChatCandidate

    results = []
    for c in raw_candidates:
        try:
            payload_dict = c.get("habit_payload", {})
            # Ensure frequency_pattern is always a dict — AI sometimes returns null
            if not payload_dict.get("frequency_pattern"):
                payload_dict = dict(payload_dict)
                payload_dict["frequency_pattern"] = {
                    "days": list(ORDERED_DAYS)
                }
            habit_payload = HabitCreate(**payload_dict)
            results.append(AIChatCandidate(
                title=c.get("title", "Habit Plan"),
                category=c.get("category", "wellness"),
                description=c.get("description", ""),
                suggested_schedule=c.get("suggested_schedule", ""),
                duration_minutes=int(c.get("duration_minutes", 30)),
                rationale=c.get("rationale", ""),
                variant=c.get("variant", "balanced"),
                habit_payload=habit_payload,
                progressions=c.get("progressions", []),
            ))
        except Exception:
            continue
    return results


def chat(
    message: str,
    draft: AIIntakeDraft,
    recent_messages: Optional[List[AIChatMessage]] = None,
) -> "AIChatResponse":
    """
    Single-turn chat handler — the public entry point for /api/ai/chat.

    Returns AIChatResponse with one of four actions:
      clarify  — Tier 1 needs more info
      generate — Tier 2 fired; candidates populated
      advise   — domain Q&A with habit pivot
      redirect — off-topic
    """
    from ..models import AIChatResponse

    if recent_messages is None:
        recent_messages = []

    provider, model = _provider_and_model()

    # --- Pre-filter (no API cost) ---
    if _is_clearly_offtopic(message):
        return AIChatResponse(
            action="redirect",
            assistant_message=(
                "I'm focused on helping you build habits. "
                "What's one thing you'd like to change about your daily routine?"
            ),
            updated_draft=draft,
            candidates=[],
        )

    # --- Mock provider short-circuit ---
    if provider == "mock":
        updated = _merge_extracted(draft, {})
        confidence = _compute_confidence(updated)
        if confidence >= _CONFIDENCE_THRESHOLD:
            return AIChatResponse(
                action="generate",
                assistant_message="Here are two plans I put together for you.",
                updated_draft=updated,
                candidates=[],
            )
        return AIChatResponse(
            action="clarify",
            assistant_message="What category does this habit fall under — fitness, study, wellness, reading, or sleep?",
            updated_draft=updated,
            candidates=[],
        )

    # --- Tier 1: extract + intent ---
    tier1 = _tier1_call(message, draft, recent_messages, model)

    action = tier1.get("action", "clarify")
    assistant_message = tier1.get("assistant_message", "")
    extracted = tier1.get("extracted", {})

    updated_draft = _merge_extracted(draft, extracted)

    # Redirect / advise — return immediately, no Tier 2
    if action in ("redirect", "advise"):
        return AIChatResponse(
            action=action,
            assistant_message=assistant_message,
            updated_draft=updated_draft,
            candidates=[],
        )

    # Compute confidence after merging this turn's extractions
    confidence = _compute_confidence(updated_draft)

    # --- Tier 2: generate when confident enough ---
    if confidence >= _CONFIDENCE_THRESHOLD:
        tier2 = _tier2_call(updated_draft, model)
        raw_candidates = tier2.get("candidates", [])
        candidates = _parse_candidates(raw_candidates)
        summary = tier2.get("summary_message", "Here are two plans I built for you.")
        return AIChatResponse(
            action="generate",
            assistant_message=summary,
            updated_draft=updated_draft,
            candidates=candidates,
        )

    # --- Still clarifying ---
    return AIChatResponse(
        action="clarify",
        assistant_message=assistant_message,
        updated_draft=updated_draft,
        candidates=[],
    )
