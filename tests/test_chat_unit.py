"""Unit tests for two-tier chat helpers — no HTTP, no DB, no OpenAI calls."""
from __future__ import annotations

import pytest

from app.models import AIIntakeDraft
from app.services.ai_pipeline import (
    _CONFIDENCE_THRESHOLD,
    _compute_confidence,
    _coerce_schedule_days,
    _is_clearly_offtopic,
    _merge_extracted,
    _parse_candidates,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EMPTY_DRAFT = AIIntakeDraft()

PARTIAL_DRAFT = AIIntakeDraft(
    goal_summary="Run every morning",
    category="fitness",
)

FULL_DRAFT = AIIntakeDraft(
    goal_summary="Study every weekday",
    category="study",
    frequency="specific_days",
    schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
    duration_minutes=60,
    experience_level="intermediate",
)

VALID_HABIT_PAYLOAD = {
    "name": "Morning Run",
    "category": "fitness",
    "description": "Daily jog",
    "trigger_type": "time",
    "trigger_value": "07:00",
    "frequency_type": "daily",
    "frequency_pattern": {"days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
    "habit_type": "binary",
    "requires_quantity": False,
    "allows_notes": True,
}


# ---------------------------------------------------------------------------
# _compute_confidence
# ---------------------------------------------------------------------------

class TestComputeConfidence:
    def test_empty_draft_is_zero(self):
        assert _compute_confidence(EMPTY_DRAFT) == 0.0

    def test_full_draft_is_one(self):
        assert _compute_confidence(FULL_DRAFT) == 1.0

    def test_partial_draft_is_between(self):
        score = _compute_confidence(PARTIAL_DRAFT)
        assert 0.0 < score < 1.0

    def test_goal_summary_weight(self):
        d = AIIntakeDraft(goal_summary="Something")
        assert _compute_confidence(d) == pytest.approx(0.25)

    def test_category_weight(self):
        d = AIIntakeDraft(category="fitness")
        assert _compute_confidence(d) == pytest.approx(0.20)

    def test_frequency_weight(self):
        d = AIIntakeDraft(frequency="daily")
        assert _compute_confidence(d) == pytest.approx(0.20)

    def test_duration_weight(self):
        d = AIIntakeDraft(duration_minutes=30)
        assert _compute_confidence(d) == pytest.approx(0.15)

    def test_experience_level_weight(self):
        d = AIIntakeDraft(experience_level="beginner")
        assert _compute_confidence(d) == pytest.approx(0.10)

    def test_schedule_days_weight_nonempty(self):
        d = AIIntakeDraft(schedule_days=["monday"])
        assert _compute_confidence(d) == pytest.approx(0.10)

    def test_schedule_days_empty_list_scores_zero(self):
        d = AIIntakeDraft(schedule_days=[])
        assert _compute_confidence(d) == pytest.approx(0.0)

    def test_threshold_not_met_without_goal(self):
        # All fields except goal_summary → 0.75, below threshold
        d = AIIntakeDraft(
            category="fitness",
            frequency="daily",
            duration_minutes=30,
            experience_level="beginner",
            schedule_days=["monday"],
        )
        assert _compute_confidence(d) < _CONFIDENCE_THRESHOLD

    def test_threshold_met_with_all_fields(self):
        assert _compute_confidence(FULL_DRAFT) >= _CONFIDENCE_THRESHOLD

    def test_returns_float(self):
        assert isinstance(_compute_confidence(EMPTY_DRAFT), float)

    # --- Tracked / cumulative habit behaviour ---

    def test_tracked_habit_target_value_fills_duration_slot(self):
        """target_value + experience_level freebie = 0.15 + 0.10 = 0.25 for tracked habits."""
        d = AIIntakeDraft(habit_type="tracked", target_value=2.0)
        assert _compute_confidence(d) == pytest.approx(0.25)

    def test_tracked_habit_experience_level_free(self):
        """experience_level is not required for tracked habits — weight awarded automatically."""
        d = AIIntakeDraft(habit_type="tracked")
        assert _compute_confidence(d) == pytest.approx(0.10)

    def test_tracked_habit_caps_at_one_without_session_fields(self):
        """A complete water habit draft (no duration, no experience_level) reaches 1.0."""
        d = AIIntakeDraft(
            habit_type="tracked",
            goal_summary="Drink 2 litres of water daily",
            category="wellness",
            frequency="daily",
            target_value=2.0,
            quantity_unit="liters",
            schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        )
        assert _compute_confidence(d) == pytest.approx(1.0)

    def test_tracked_habit_meets_threshold_without_duration_or_experience(self):
        """Water habit should cross 0.8 and trigger Tier 2."""
        d = AIIntakeDraft(
            habit_type="tracked",
            goal_summary="Drink 9 glasses of water a day",
            category="wellness",
            frequency="daily",
            target_value=9.0,
            quantity_unit="glasses",
            schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        )
        assert _compute_confidence(d) >= _CONFIDENCE_THRESHOLD

    def test_session_habit_still_requires_duration(self):
        """A binary/session habit without duration_minutes should not get that weight."""
        d = AIIntakeDraft(
            habit_type="binary",
            goal_summary="Run in the morning",
            category="fitness",
            frequency="specific_days",
        )
        score = _compute_confidence(d)
        # goal(0.25) + category(0.20) + frequency(0.20) = 0.65, no duration credit
        assert score == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# _is_clearly_offtopic
# ---------------------------------------------------------------------------

class TestIsClealryOfftopic:
    def test_weather_is_offtopic(self):
        assert _is_clearly_offtopic("What's the weather like today?") is True

    def test_crypto_is_offtopic(self):
        assert _is_clearly_offtopic("Should I buy bitcoin?") is True

    def test_politics_is_offtopic(self):
        assert _is_clearly_offtopic("Who should I vote for in the election?") is True

    def test_habit_message_is_not_offtopic(self):
        assert _is_clearly_offtopic("I want to build a workout habit") is False

    def test_study_message_is_not_offtopic(self):
        assert _is_clearly_offtopic("Help me study every day") is False

    def test_generic_message_is_not_offtopic(self):
        # Ambiguous message with no keyword match — should not be flagged
        assert _is_clearly_offtopic("I need help with something") is False

    def test_habit_keyword_overrides_offtopic_keyword(self):
        # "morning routine" contains both a habit keyword and could overlap —
        # habit keyword should win and return False
        assert _is_clearly_offtopic("my morning routine includes football practice") is False

    def test_empty_string_is_not_offtopic(self):
        assert _is_clearly_offtopic("") is False

    def test_case_insensitive(self):
        assert _is_clearly_offtopic("WEATHER forecast?") is True


# ---------------------------------------------------------------------------
# _merge_extracted
# ---------------------------------------------------------------------------

class TestMergeExtracted:
    def test_empty_extracted_returns_same_draft(self):
        result = _merge_extracted(PARTIAL_DRAFT, {})
        assert result.goal_summary == PARTIAL_DRAFT.goal_summary
        assert result.category == PARTIAL_DRAFT.category

    def test_extracted_field_overwrites_draft(self):
        draft = AIIntakeDraft(category="fitness")
        result = _merge_extracted(draft, {"category": "study"})
        assert result.category == "study"

    def test_extracted_adds_new_field(self):
        draft = AIIntakeDraft(goal_summary="Run daily")
        result = _merge_extracted(draft, {"category": "fitness"})
        assert result.goal_summary == "Run daily"
        assert result.category == "fitness"

    def test_none_value_does_not_overwrite(self):
        draft = AIIntakeDraft(category="fitness")
        result = _merge_extracted(draft, {"category": None})
        assert result.category == "fitness"

    def test_disallowed_key_ignored(self):
        draft = AIIntakeDraft()
        result = _merge_extracted(draft, {"id": 999, "user_id": 1})
        assert not hasattr(result, "id") or getattr(result, "id", None) is None

    def test_schedule_days_merged(self):
        draft = AIIntakeDraft()
        result = _merge_extracted(draft, {"schedule_days": ["monday", "friday"]})
        assert result.schedule_days == ["monday", "friday"]

    def test_duration_minutes_merged(self):
        draft = AIIntakeDraft(duration_minutes=30)
        result = _merge_extracted(draft, {"duration_minutes": 90})
        assert result.duration_minutes == 90

    def test_existing_unrelated_fields_preserved(self):
        draft = AIIntakeDraft(
            goal_summary="Run daily",
            category="fitness",
            frequency="daily",
        )
        result = _merge_extracted(draft, {"duration_minutes": 45})
        assert result.goal_summary == "Run daily"
        assert result.category == "fitness"
        assert result.frequency == "daily"
        assert result.duration_minutes == 45


# ---------------------------------------------------------------------------
# _parse_candidates
# ---------------------------------------------------------------------------

class TestParseCandidates:
    def test_empty_list_returns_empty(self):
        assert _parse_candidates([]) == []

    def test_valid_candidate_parsed(self):
        raw = [{
            "title": "Morning Run",
            "category": "fitness",
            "description": "Daily jog",
            "suggested_schedule": "07:00 daily",
            "duration_minutes": 30,
            "rationale": "Good for cardio",
            "variant": "balanced",
            "habit_payload": VALID_HABIT_PAYLOAD,
            "progressions": [{"week": 1, "description": "Start easy"}],
        }]
        results = _parse_candidates(raw)
        assert len(results) == 1
        c = results[0]
        assert c.title == "Morning Run"
        assert c.variant == "balanced"
        assert c.duration_minutes == 30
        assert c.progressions == [{"week": 1, "description": "Start easy"}]

    def test_two_variants_parsed(self):
        balanced = {**{"title": "Run", "category": "fitness", "description": "", "suggested_schedule": "",
                       "duration_minutes": 30, "rationale": "", "variant": "balanced", "progressions": []},
                    "habit_payload": VALID_HABIT_PAYLOAD}
        ambitious = {**balanced, "variant": "ambitious", "duration_minutes": 60}
        results = _parse_candidates([balanced, ambitious])
        assert len(results) == 2
        variants = {c.variant for c in results}
        assert variants == {"balanced", "ambitious"}

    def test_malformed_candidate_skipped(self):
        """A candidate missing required habit_payload fields is silently dropped."""
        bad = {"title": "Bad", "variant": "balanced", "habit_payload": {"name": "X"}}  # missing required fields
        good = {
            "title": "Good",
            "category": "fitness",
            "description": "",
            "suggested_schedule": "",
            "duration_minutes": 30,
            "rationale": "",
            "variant": "balanced",
            "habit_payload": VALID_HABIT_PAYLOAD,
            "progressions": [],
        }
        results = _parse_candidates([bad, good])
        assert len(results) == 1
        assert results[0].title == "Good"

    def test_all_malformed_returns_empty(self):
        bad = [{"title": "X", "habit_payload": {}} for _ in range(3)]
        assert _parse_candidates(bad) == []

    def test_missing_optional_fields_use_defaults(self):
        minimal = {
            "habit_payload": VALID_HABIT_PAYLOAD,
        }
        results = _parse_candidates([minimal])
        assert len(results) == 1
        c = results[0]
        assert c.title == "Habit Plan"       # default
        assert c.category == "wellness"      # default
        assert c.variant == "balanced"       # default
        assert c.duration_minutes == 30      # default
        assert c.progressions == []

    def test_habit_payload_fields_accessible(self):
        raw = [{
            "title": "Study Session",
            "category": "study",
            "description": "Deep work block",
            "suggested_schedule": "09:00",
            "duration_minutes": 90,
            "rationale": "Focus time",
            "variant": "ambitious",
            "habit_payload": {
                **VALID_HABIT_PAYLOAD,
                "name": "Deep Work",
                "category": "study",
            },
            "progressions": [],
        }]
        results = _parse_candidates(raw)
        assert results[0].habit_payload.name == "Deep Work"
        assert results[0].habit_payload.category == "study"

    def test_null_frequency_pattern_fallback(self):
        """Regression: AI returns frequency_pattern=null for daily habits — must not drop candidate."""
        payload_no_freq = {
            "name": "Daily Run",
            "category": "fitness",
            "description": "Run every day",
            "trigger_type": "time",
            "trigger_value": "07:00",
            "frequency_type": "daily",
            "frequency_pattern": None,  # AI bug — returns null instead of dict
            "requires_quantity": False,
            "allows_notes": True,
        }
        raw = [{
            "title": "Daily Run",
            "category": "fitness",
            "description": "Run every day",
            "suggested_schedule": "daily",
            "duration_minutes": 30,
            "rationale": "Good cardio",
            "variant": "balanced",
            "habit_payload": payload_no_freq,
            "progressions": [],
        }]
        results = _parse_candidates(raw)
        assert len(results) == 1
        assert results[0].habit_payload.frequency_pattern == {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        }


# ---------------------------------------------------------------------------
# _coerce_schedule_days — the bug that caused the 500
# ---------------------------------------------------------------------------

class TestCoerceScheduleDays:
    def test_string_range_monday_through_saturday(self):
        result = _coerce_schedule_days("Monday through Saturday")
        assert result == ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

    def test_string_range_monday_to_friday(self):
        result = _coerce_schedule_days("Monday to Friday")
        assert result == ["monday", "tuesday", "wednesday", "thursday", "friday"]

    def test_comma_separated_string(self):
        result = _coerce_schedule_days("Mon, Wed, Fri")
        assert result == ["monday", "wednesday", "friday"]

    def test_slash_separated_string(self):
        result = _coerce_schedule_days("Mon/Wed/Fri")
        assert result == ["monday", "wednesday", "friday"]

    def test_list_of_capitalized_names(self):
        result = _coerce_schedule_days(["Monday", "Wednesday", "Friday"])
        assert result == ["monday", "wednesday", "friday"]

    def test_list_already_lowercase(self):
        result = _coerce_schedule_days(["monday", "thursday"])
        assert result == ["monday", "thursday"]

    def test_weekdays_shorthand(self):
        result = _coerce_schedule_days("weekdays")
        assert result == ["monday", "tuesday", "wednesday", "thursday", "friday"]

    def test_weekend_shorthand(self):
        result = _coerce_schedule_days("weekends")
        assert result == ["saturday", "sunday"]

    def test_daily_shorthand(self):
        result = _coerce_schedule_days("daily")
        assert len(result) == 7

    def test_invalid_string_returns_empty(self):
        result = _coerce_schedule_days("sometime next week")
        assert result == []

    def test_invalid_type_returns_empty(self):
        assert _coerce_schedule_days(42) == []

    def test_merge_extracted_with_string_schedule_days(self):
        """Regression: the exact input that caused the 500."""
        draft = AIIntakeDraft()
        result = _merge_extracted(draft, {"schedule_days": "Monday through Saturday"})
        assert result.schedule_days == [
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
        ]

    def test_merge_extracted_invalid_schedule_days_ignored(self):
        """If coercion yields nothing, the existing draft value is preserved."""
        draft = AIIntakeDraft(schedule_days=["monday"])
        result = _merge_extracted(draft, {"schedule_days": "some nonsense"})
        assert result.schedule_days == ["monday"]
