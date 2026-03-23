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
    assert data["ready_for_confirmation"] is False
    assert "duration_minutes" in data["missing_fields"]
    assert data["updated_draft"]["schedule_days"] == [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    assert "how long should each session be" in data["assistant_message"].lower()


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
