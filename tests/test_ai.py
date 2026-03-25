"""AI pipeline tests — AI_PROVIDER=mock is set in conftest.py before app loads."""
from __future__ import annotations

import pytest

from tests.helpers import get_token, auth_headers, habit_payload


ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

INTAKE_REQUEST = {
    "recent_messages": [],
    "current_draft": {
        "goal_summary": None,
        "habit_description": None,
        "frequency": None,
        "schedule_text": None,
        "schedule_days": [],
        "duration_minutes": None,
        "experience_level": None,
        "category": None,
        "preferred_time": "flexible",
        "available_time": 15,
    },
    "latest_user_message": "I want to run every morning",
}

DRAFT = {
    "goal_summary": "Run every morning",
    "habit_description": "Morning jog",
    "frequency": "daily",
    "schedule_text": "every day",
    "schedule_days": ALL_DAYS,
    "duration_minutes": 30,
    "experience_level": "beginner",
    "category": "fitness",
    "preferred_time": "morning",
    "available_time": 30,
}


# ---------------------------------------------------------------------------
# POST /api/ai/intake
# ---------------------------------------------------------------------------

def test_intake_requires_auth(client):
    r = client.post("/api/ai/intake", json=INTAKE_REQUEST)
    assert r.status_code in (401, 403)


def test_intake_returns_assistant_message(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/intake",
        json=INTAKE_REQUEST,
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert "assistant_message" in body
    assert "updated_draft" in body
    assert "ready_for_confirmation" in body
    assert "needs_clarification" in body


def test_intake_missing_latest_message(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/intake",
        json={"recent_messages": [], "current_draft": {}},
        headers=auth_headers(token),
    )
    assert r.status_code == 422


def test_intake_with_goal(client):
    token = get_token(client)
    payload = {
        **INTAKE_REQUEST,
        "latest_user_message": "I want to study for 2 hours every weekday",
    }
    r = client.post("/api/ai/intake", json=payload, headers=auth_headers(token))
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/ai/generate-plan
# ---------------------------------------------------------------------------

def test_generate_plan_requires_auth(client):
    r = client.post("/api/ai/generate-plan", json={
        "user_goal": "Run every day",
        "category": "fitness",
        "context": None,
    })
    assert r.status_code in (401, 403)


def test_generate_plan_mock(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/generate-plan",
        json={"user_goal": "Run every day", "category": "fitness", "context": None},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "habit_payload" in body
    assert "progressions" in body
    assert body["provider"] == "mock"


def test_generate_plan_invalid_category(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/generate-plan",
        json={"user_goal": "Bake bread", "category": "invalid_cat", "context": None},
        headers=auth_headers(token),
    )
    # pipeline should either 200 with fallback or 422/400
    assert r.status_code in (200, 400, 422)


def test_generate_plan_with_context(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/generate-plan",
        json={
            "user_goal": "Meditate daily",
            "category": "wellness",
            "context": {
                "experience_level": "beginner",
                "available_time": 15,
                "preferred_time": "morning",
            },
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


# ---------------------------------------------------------------------------
# POST /api/ai/generate-plan-from-draft
# ---------------------------------------------------------------------------

def test_generate_plan_from_draft(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/generate-plan-from-draft",
        json={"draft": DRAFT},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "habit_payload" in body


def test_generate_plan_from_draft_requires_auth(client):
    r = client.post("/api/ai/generate-plan-from-draft", json={"draft": DRAFT})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/ai/generate-and-create
# ---------------------------------------------------------------------------

def test_generate_and_create(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/generate-and-create",
        json={"user_goal": "Sleep better", "category": "sleep", "context": None},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["success"] is True
    assert "habit" in body
    assert body["habit"]["id"] is not None


def test_generate_and_create_habit_appears_in_list(client):
    token = get_token(client)
    client.post(
        "/api/ai/generate-and-create",
        json={"user_goal": "Read every day", "category": "reading", "context": None},
        headers=auth_headers(token),
    )
    r = client.get("/api/habits/", headers=auth_headers(token))
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ---------------------------------------------------------------------------
# POST /api/ai/generate-and-create-from-draft
# ---------------------------------------------------------------------------

def test_generate_and_create_from_draft(client):
    token = get_token(client)
    r = client.post(
        "/api/ai/generate-and-create-from-draft",
        json={"draft": DRAFT},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["success"] is True
    assert "habit" in body


def test_generate_and_create_from_draft_requires_auth(client):
    r = client.post(
        "/api/ai/generate-and-create-from-draft",
        json={"draft": DRAFT},
    )
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/ai/revise-plan
# ---------------------------------------------------------------------------

def test_revise_plan(client):
    token = get_token(client)

    # First generate a plan
    plan_r = client.post(
        "/api/ai/generate-plan-from-draft",
        json={"draft": DRAFT},
        headers=auth_headers(token),
    )
    assert plan_r.status_code == 200
    plan_body = plan_r.json()

    # Revise it
    revise_payload = {
        "draft": DRAFT,
        "current_plan": {
            "habit_payload": plan_body["habit_payload"],
            "progressions": plan_body["progressions"],
            "raw_plan": plan_body.get("raw_plan", {}),
        },
        "critique": "make it more structured",
        "recent_messages": [],
    }
    r = client.post(
        "/api/ai/revise-plan",
        json=revise_payload,
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["action"] in ("plan_tweak", "reopen_intake")


def test_revise_plan_requires_auth(client):
    r = client.post("/api/ai/revise-plan", json={
        "draft": DRAFT,
        "current_plan": {"habit_payload": {}, "progressions": [], "raw_plan": {}},
        "critique": "more variety",
        "recent_messages": [],
    })
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Habit payload validation (frequency_pattern invariant)
# ---------------------------------------------------------------------------

def test_ai_plan_has_valid_frequency_pattern(client):
    """Generated plan must always include a valid frequency_pattern."""
    token = get_token(client)
    r = client.post(
        "/api/ai/generate-plan",
        json={"user_goal": "Run every day", "category": "fitness", "context": None},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    payload = r.json()["habit_payload"]
    # frequency_pattern must be a dict with "days" key
    fp = payload.get("frequency_pattern")
    assert isinstance(fp, dict), f"frequency_pattern should be dict, got: {fp!r}"
    assert "days" in fp
    assert isinstance(fp["days"], list)
    assert len(fp["days"]) > 0
