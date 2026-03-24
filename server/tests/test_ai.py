import pytest

from .helpers import (
    ai_payload,
    auth_headers,
    intake_draft,
    intake_payload,
    plan_snapshot_payload,
    register_user,
)


@pytest.fixture(autouse=True)
def mock_ai_settings(monkeypatch):
    from server.app.services import ai_pipeline

    monkeypatch.setattr(ai_pipeline.settings, "AI_PROVIDER", "mock", raising=False)
    monkeypatch.setattr(ai_pipeline.settings, "OPENAI_MODEL", "gpt-4o-mini-test", raising=False)
    monkeypatch.setattr(ai_pipeline.settings, "OPENAI_API_KEY", "", raising=False)


def test_generate_plan_requires_auth(client):
    response = client.post("/api/ai/generate-plan", json=ai_payload())
    assert response.status_code in (401, 403)


def test_intake_requires_auth(client):
    response = client.post("/api/ai/intake", json=intake_payload("I want to start running"))
    assert response.status_code in (401, 403)


def test_intake_returns_missing_field_follow_up(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/intake",
        json=intake_payload("I want to start running regularly"),
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["updated_draft"]["goal_summary"]
    assert "frequency" in data["missing_fields"]
    assert data["ready_for_confirmation"] is False
    assert data["assistant_message"]


def test_intake_requests_schedule_days_when_frequency_is_count_based(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/intake",
        json=intake_payload("I want to start running 3 times a week for 20 minutes and I'm a beginner"),
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    assert data["ready_for_confirmation"] is False
    assert "schedule" in data["missing_fields"]
    assert data["updated_draft"]["duration_minutes"] == 20
    assert "days of the week" in data["assistant_message"].lower()


def test_intake_requests_duration_when_schedule_is_known(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/intake",
        json=intake_payload("I want to read every day and I'm a beginner"),
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    # With experience inferencing, duration is auto-filled for beginner+reading so the draft is complete
    assert data["updated_draft"]["schedule_days"] == [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    # duration_minutes is now inferred from experience level defaults
    assert data["updated_draft"]["duration_minutes"] is not None


def test_intake_ready_for_confirmation_returns_summary(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/intake",
        json=intake_payload(
            "I want to read every day for ten minutes and I'm a beginner",
            current_draft=intake_draft(),
        ),
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    assert data["ready_for_confirmation"] is True
    assert data["confirmation_summary"]
    assert data["updated_draft"]["category"] == "reading"
    assert data["updated_draft"]["experience_level"] == "beginner"
    assert data["updated_draft"]["frequency"] == "every day"
    assert data["updated_draft"]["duration_minutes"] == 10
    assert data["updated_draft"]["schedule_days"] == [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    assert "Days: Every day" in data["confirmation_summary"]
    assert "Duration: 10 minutes" in data["confirmation_summary"]


def test_generate_plan_in_mock_mode_returns_plan_without_creating_habit(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    before_response = client.get("/api/habits/", headers=auth_headers(token))
    assert before_response.status_code == 200
    assert before_response.json() == []

    response = client.post(
        "/api/ai/generate-plan",
        json=ai_payload(user_goal="I want to read for ten minutes every day", category="reading"),
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["provider"] == "mock"
    assert data["model"] == "gpt-4o-mini-test"
    assert data["habit_payload"]["category"] == "reading"
    assert data["habit_payload"]["name"]
    assert data["progressions"]

    after_response = client.get("/api/habits/", headers=auth_headers(token))
    assert after_response.status_code == 200
    assert after_response.json() == []


def test_generate_plan_from_draft_returns_plan(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/generate-plan-from-draft",
        json={
            "draft": intake_draft(
                goal_summary="Build a steady reading habit",
                habit_description="Read a nonfiction book for a focused block",
                frequency="weekdays",
                schedule_text="monday, tuesday, wednesday, thursday, friday",
                schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
                duration_minutes=20,
                experience_level="beginner",
                category="reading",
            )
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["habit_payload"]["category"] == "reading"
    assert data["habit_payload"]["frequency_type"] == "custom"
    assert data["progressions"]


def test_generate_and_create_from_draft_persists_habit(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/generate-and-create-from-draft",
        json={
            "draft": intake_draft(
                goal_summary="Build a steady running habit",
                habit_description="Run three times a week without burning out",
                frequency="3 times per week",
                schedule_text="monday, wednesday, friday",
                schedule_days=["monday", "wednesday", "friday"],
                duration_minutes=20,
                experience_level="beginner",
                category="fitness",
            )
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201

    data = response.json()
    assert data["success"] is True
    assert data["habit"]["category"] == "fitness"
    assert data["habit"]["user_id"]
    assert data["progressions"]

    list_response = client.get("/api/habits/", headers=auth_headers(token))
    assert list_response.status_code == 200
    habits = list_response.json()
    assert len(habits) == 1
    assert habits[0]["id"] == data["habit"]["id"]


def test_revise_plan_returns_tweaked_preview_when_critique_is_non_structural(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/revise-plan",
        json={
            "draft": intake_draft(
                goal_summary="Build a reading habit",
                habit_description="Read before work",
                frequency="every day",
                schedule_text="every day",
                schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                duration_minutes=10,
                experience_level="beginner",
                category="reading",
            ),
            "current_plan": plan_snapshot_payload(),
            "critique": "Make it a little gentler and less intense.",
            "recent_messages": [
                {"role": "assistant", "content": "What would you like to change?"},
                {"role": "user", "content": "Make it a little gentler and less intense."},
            ],
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["action"] == "plan_tweak"
    assert data["plan_tweak"]["habit_payload"]["category"] == "reading"
    assert data["plan_tweak"]["progressions"]


def test_revise_plan_reopens_intake_when_structured_fields_change(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    response = client.post(
        "/api/ai/revise-plan",
        json={
            "draft": intake_draft(
                goal_summary="Build a reading habit",
                habit_description="Read before work",
                frequency="every day",
                schedule_text="every day",
                schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                duration_minutes=10,
                experience_level="beginner",
                category="reading",
            ),
            "current_plan": plan_snapshot_payload(),
            "critique": "Actually, make it weekdays only instead.",
            "recent_messages": [
                {"role": "assistant", "content": "What would you like to change?"},
                {"role": "user", "content": "Actually, make it weekdays only instead."},
            ],
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["action"] == "reopen_intake"
    assert data["reopen_intake"]["ready_for_confirmation"] is True
    assert data["reopen_intake"]["updated_draft"]["frequency"] == "weekdays"


# ---------------------------------------------------------------------------
# Intent classification tests
# ---------------------------------------------------------------------------

class TestIntentClassification:
    """Tests for classify_intent_mock (rule-based, used in mock AI mode)."""

    def test_on_topic_basic_habit(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("I want to start running every morning") == "on_topic"

    def test_on_topic_vague_but_habit_related(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("I want to be more consistent with my workouts") == "on_topic"

    def test_on_topic_emotional_context(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        # Emotional messages about habits should still be on_topic
        assert classify_intent_mock("I've been struggling to stay consistent lately") == "on_topic"

    def test_off_topic_weather(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("What is the weather like today?") == "off_topic"

    def test_off_topic_coding(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("Can you write code to sort a list?") == "off_topic"

    def test_off_topic_joke(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("Tell me a joke please") == "off_topic"

    def test_sensitive_injury(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("I'm recovering from surgery and want to start exercising") == "sensitive"

    def test_sensitive_mental_health(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("I've been dealing with depression and want to build better habits") == "sensitive"

    def test_sensitive_eating_disorder(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("I have an eating disorder but want to eat more regularly") == "sensitive"

    def test_multi_habit_two_categories(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("I want to start running and also want to meditate every day") == "multi_habit"

    def test_multi_habit_in_addition(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        assert classify_intent_mock("I want to read more books, in addition I want to exercise at the gym") == "multi_habit"

    def test_single_habit_not_multi(self):
        from server.app.services.ai_pipeline import classify_intent_mock
        # Only one category mentioned — should be on_topic not multi_habit
        assert classify_intent_mock("I want to run 3 times a week and also track my miles") == "on_topic"


class TestIntakeIntentRouting:
    """Integration tests: off-topic and sensitive inputs get appropriate redirects via intake endpoint."""

    def test_off_topic_input_returns_redirect_message(self, client):
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        response = client.post(
            "/api/ai/intake",
            json=intake_payload("What is the weather like today?"),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "off_topic"
        assert data["ready_for_confirmation"] is False
        assert "habit" in data["assistant_message"].lower()

    def test_sensitive_input_returns_safety_message(self, client):
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        response = client.post(
            "/api/ai/intake",
            json=intake_payload("I'm recovering from surgery and want to start exercising again"),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "sensitive"
        assert data["ready_for_confirmation"] is False
        assert any(word in data["assistant_message"].lower() for word in ["doctor", "therapist", "support", "professional"])

    def test_multi_habit_input_prompts_focus(self, client):
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        response = client.post(
            "/api/ai/intake",
            json=intake_payload("I want to start running and also want to meditate daily"),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "multi_habit"
        assert data["ready_for_confirmation"] is False
        assert any(word in data["assistant_message"].lower() for word in ["one", "focus", "which"])

    def test_on_topic_input_has_on_topic_intent(self, client):
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        response = client.post(
            "/api/ai/intake",
            json=intake_payload("I want to start running every morning"),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "on_topic"


# ---------------------------------------------------------------------------
# Realism check tests
# ---------------------------------------------------------------------------

class TestRealismCheck:
    """Tests for the rule-based realism check."""

    def test_realistic_beginner_fitness(self):
        from server.app.services.ai_pipeline import check_realism
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Run regularly",
            experience_level="beginner",
            category="fitness",
            duration_minutes=30,
            schedule_days=["monday", "wednesday", "friday"],
            frequency="3 times per week",
        )
        result = check_realism(draft)
        assert result.is_realistic is True
        assert result.warning_message is None

    def test_unrealistic_duration_beginner_fitness(self):
        from server.app.services.ai_pipeline import check_realism
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Work out hard",
            experience_level="beginner",
            category="fitness",
            duration_minutes=120,  # exceeds 60 min beginner cap
            schedule_days=["monday", "wednesday", "friday"],
            frequency="3 times per week",
        )
        result = check_realism(draft)
        assert result.is_realistic is False
        assert result.warning_message is not None
        assert "beginner" in result.warning_message.lower()
        assert result.suggested_duration_minutes == 60

    def test_unrealistic_days_beginner_fitness(self):
        from server.app.services.ai_pipeline import check_realism
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Work out every day",
            experience_level="beginner",
            category="fitness",
            duration_minutes=30,
            schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],  # 7 days > 5 day cap
            frequency="every day",
        )
        result = check_realism(draft)
        assert result.is_realistic is False
        assert result.suggested_days_per_week == 5

    def test_unrealistic_duration_and_days(self):
        from server.app.services.ai_pipeline import check_realism
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Intense daily workout",
            experience_level="beginner",
            category="fitness",
            duration_minutes=120,
            schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            frequency="every day",
        )
        result = check_realism(draft)
        assert result.is_realistic is False
        assert result.suggested_duration_minutes == 60
        assert result.suggested_days_per_week == 5

    def test_advanced_user_higher_caps(self):
        from server.app.services.ai_pipeline import check_realism
        from server.app.models import AIIntakeDraft
        # Advanced fitness user — 120 min is within the 180 min cap
        draft = AIIntakeDraft(
            goal_summary="Train hard",
            experience_level="advanced",
            category="fitness",
            duration_minutes=120,
            schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
            frequency="5 times per week",
        )
        result = check_realism(draft)
        assert result.is_realistic is True

    def test_missing_experience_level_skips_check(self):
        from server.app.services.ai_pipeline import check_realism
        from server.app.models import AIIntakeDraft
        # Without experience level we can't assess realism — should pass through
        draft = AIIntakeDraft(
            goal_summary="Work out",
            category="fitness",
            duration_minutes=200,
            schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        )
        result = check_realism(draft)
        assert result.is_realistic is True

    def test_realism_warning_surfaces_in_intake_response(self, client):
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        # Provide a complete draft that triggers the realism check
        response = client.post(
            "/api/ai/intake",
            json=intake_payload(
                "I want to work out for 2 hours every single day and I'm a total beginner",
                current_draft=intake_draft(
                    goal_summary="Work out intensely every day",
                    experience_level="beginner",
                    category="fitness",
                    duration_minutes=120,
                    schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                    frequency="every day",
                    schedule_text="every day",
                ),
            ),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["realism_warning"] is not None
        assert "beginner" in data["realism_warning"].lower()


# ---------------------------------------------------------------------------
# Experience inferencing tests
# ---------------------------------------------------------------------------

class TestExperienceInferencing:
    """Tests for automatic frequency/duration inference from experience level."""

    def test_infers_duration_for_beginner_fitness(self):
        from server.app.services.ai_pipeline import _infer_defaults_from_experience
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Start running",
            experience_level="beginner",
            category="fitness",
        )
        result = _infer_defaults_from_experience(draft)
        assert result.duration_minutes == 20  # beginner fitness default

    def test_infers_frequency_for_advanced_fitness(self):
        from server.app.services.ai_pipeline import _infer_defaults_from_experience
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Keep training",
            experience_level="advanced",
            category="fitness",
        )
        result = _infer_defaults_from_experience(draft)
        assert len(result.schedule_days) == 5  # advanced fitness = 5 days/week

    def test_does_not_override_existing_frequency(self):
        from server.app.services.ai_pipeline import _infer_defaults_from_experience
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Run daily",
            experience_level="beginner",
            category="fitness",
            frequency="every day",
            schedule_days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        )
        result = _infer_defaults_from_experience(draft)
        # User explicitly said every day — should NOT be overridden
        assert result.schedule_days == ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    def test_does_not_override_existing_duration(self):
        from server.app.services.ai_pipeline import _infer_defaults_from_experience
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Quick runs",
            experience_level="beginner",
            category="fitness",
            duration_minutes=10,
        )
        result = _infer_defaults_from_experience(draft)
        assert result.duration_minutes == 10  # user's value preserved

    def test_no_inference_without_category(self):
        from server.app.services.ai_pipeline import _infer_defaults_from_experience
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Build a habit",
            experience_level="beginner",
        )
        result = _infer_defaults_from_experience(draft)
        assert result.duration_minutes is None

    def test_no_inference_without_experience(self):
        from server.app.services.ai_pipeline import _infer_defaults_from_experience
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Start running",
            category="fitness",
        )
        result = _infer_defaults_from_experience(draft)
        assert result.duration_minutes is None

    def test_intermediate_wellness_infers_daily(self):
        from server.app.services.ai_pipeline import _infer_defaults_from_experience
        from server.app.models import AIIntakeDraft
        draft = AIIntakeDraft(
            goal_summary="Meditate",
            experience_level="intermediate",
            category="wellness",
        )
        result = _infer_defaults_from_experience(draft)
        assert len(result.schedule_days) == 7  # wellness defaults to daily
        assert result.duration_minutes == 15

    def test_experience_infers_fills_missing_fields_reducing_questions(self, client):
        """When experience + category are known, fewer fields should remain missing."""
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        # User says they want to run and they're advanced — frequency/duration should be inferred
        response = client.post(
            "/api/ai/intake",
            json=intake_payload(
                "I want to start running again. I've been doing it for years, very experienced.",
                current_draft=intake_draft(
                    goal_summary="Start running again",
                    category="fitness",
                    experience_level="advanced",
                ),
            ),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        data = response.json()
        # Because experience + category are known, frequency/duration should be inferred
        # so schedule_days and duration_minutes should be populated
        assert data["updated_draft"]["duration_minutes"] is not None
        assert data["updated_draft"]["schedule_days"]


# ---------------------------------------------------------------------------
# Output validation tests
# ---------------------------------------------------------------------------

class TestOutputValidation:
    """Tests for plan field validation."""

    def test_valid_plan_has_no_errors(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput, ProgressionStep
        plan = HabitPlanLLMOutput(
            habit_name="Morning Run",
            category="fitness",
            description="Go for a run",
            trigger_value="07:00",
            frequency_type="custom",
            frequency_pattern={"days": ["monday", "wednesday", "friday"]},
            motivation_statement="Build consistency",
            progressions=[ProgressionStep(week=2, description="Add 5 minutes")],
        )
        assert _validate_plan_fields(plan) == []

    def test_empty_habit_name_is_invalid(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput, ProgressionStep
        plan = HabitPlanLLMOutput(
            habit_name="",
            category="fitness",
            description="Run",
            trigger_value="07:00",
            frequency_type="daily",
            motivation_statement="Be consistent",
            progressions=[ProgressionStep(week=2, description="More")],
        )
        errors = _validate_plan_fields(plan)
        assert any("habit_name" in e for e in errors)

    def test_invalid_trigger_value_format(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput, ProgressionStep
        plan = HabitPlanLLMOutput(
            habit_name="Morning Run",
            category="fitness",
            description="Run",
            trigger_value="7am",  # invalid format
            frequency_type="daily",
            motivation_statement="Run daily",
            progressions=[ProgressionStep(week=2, description="More")],
        )
        errors = _validate_plan_fields(plan)
        assert any("trigger_value" in e for e in errors)

    def test_custom_frequency_without_days_is_invalid(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput, ProgressionStep
        plan = HabitPlanLLMOutput(
            habit_name="Morning Run",
            category="fitness",
            description="Run",
            trigger_value="07:00",
            frequency_type="custom",
            frequency_pattern={"days": []},  # empty days
            motivation_statement="Run consistently",
            progressions=[ProgressionStep(week=2, description="More")],
        )
        errors = _validate_plan_fields(plan)
        assert any("frequency_pattern" in e for e in errors)

    def test_invalid_day_name_in_custom_frequency(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput, ProgressionStep
        plan = HabitPlanLLMOutput(
            habit_name="Run",
            category="fitness",
            description="Go run",
            trigger_value="07:00",
            frequency_type="custom",
            frequency_pattern={"days": ["monday", "funday"]},  # "funday" is invalid
            motivation_statement="Stay active",
            progressions=[ProgressionStep(week=2, description="More")],
        )
        errors = _validate_plan_fields(plan)
        assert any("invalid day" in e for e in errors)

    def test_empty_motivation_statement_is_invalid(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput, ProgressionStep
        plan = HabitPlanLLMOutput(
            habit_name="Morning Run",
            category="fitness",
            description="Run",
            trigger_value="07:00",
            frequency_type="daily",
            motivation_statement="",
            progressions=[ProgressionStep(week=2, description="More")],
        )
        errors = _validate_plan_fields(plan)
        assert any("motivation_statement" in e for e in errors)

    def test_no_progressions_is_invalid(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput
        plan = HabitPlanLLMOutput(
            habit_name="Morning Run",
            category="fitness",
            description="Run",
            trigger_value="07:00",
            frequency_type="daily",
            motivation_statement="Stay active",
            progressions=[],
        )
        errors = _validate_plan_fields(plan)
        assert any("progressions" in e for e in errors)

    def test_daily_frequency_type_is_valid(self):
        from server.app.services.ai_pipeline import _validate_plan_fields, HabitPlanLLMOutput, ProgressionStep
        plan = HabitPlanLLMOutput(
            habit_name="Morning Run",
            category="fitness",
            description="Run daily",
            trigger_value="07:00",
            frequency_type="daily",
            frequency_pattern=None,
            motivation_statement="Be consistent",
            progressions=[ProgressionStep(week=2, description="Go longer")],
        )
        assert _validate_plan_fields(plan) == []


# ---------------------------------------------------------------------------
# Context windowing tests
# ---------------------------------------------------------------------------

class TestContextWindowing:
    """Tests that the server enforces a maximum message history window."""

    def test_intake_accepts_long_history_without_error(self, client):
        """Server should handle oversized histories by windowing, not crashing."""
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        # Send 20 messages — more than MAX_RECENT_MESSAGES (10)
        long_history = [
            {"role": "assistant" if i % 2 == 0 else "user", "content": f"Message {i}"}
            for i in range(20)
        ]
        response = client.post(
            "/api/ai/intake",
            json=intake_payload(
                "I want to read every day",
                recent_messages=long_history,
            ),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_intake_with_empty_history_works(self, client):
        register_response, _, _ = register_user(client)
        token = register_response.json()["access_token"]

        response = client.post(
            "/api/ai/intake",
            json=intake_payload("I want to meditate every morning", recent_messages=[]),
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
