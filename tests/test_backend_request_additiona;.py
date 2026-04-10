from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import get_session
from app.main import app
from app.models import AIIntakeDraft, CommunityPost, Completion, Habit, User
from app.routes import ai as ai_routes
from app.routes import debug as debug_routes
from app.services.ai_pipeline import (
    AIPipelineConfigError,
    AIPipelineError,
    AIPipelineGenerationError,
)
from tests.helpers import ALL_DAYS, auth_headers, habit_payload, register_user


@pytest.fixture(name="client", scope="function")
def client_without_startup(engine):
    def _get_test_session():
        with Session(engine) as session:
            yield session

    original_startup = list(app.router.on_startup)
    app.router.on_startup = []
    app.dependency_overrides[get_session] = _get_test_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.router.on_startup = original_startup
        app.dependency_overrides.clear()


def _register_and_login(
    client,
    email: str,
    password: str = "password123",
    name: str = "Test User",
) -> tuple[dict, dict]:
    response = register_user(client, email=email, password=password, name=name)
    assert response.status_code == 201, response.text
    body = response.json()
    token = body["access_token"]
    return body["user"], auth_headers(token)


def _create_habit(client, headers: dict, **overrides) -> dict:
    response = client.post("/api/habits/", json=habit_payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _send_friend_request(client, headers: dict, receiver_id: int, message: str | None = None):
    params = {"receiver_id": receiver_id}
    if message is not None:
        params["message"] = message
    return client.post("/api/friends/requests", params=params, headers=headers)


def _candidate_payload(**overrides) -> dict:
    base = {
        "title": "Morning Run",
        "category": "fitness",
        "description": "Run for twenty minutes",
        "suggested_schedule": "Mon, Wed, Fri at 07:00",
        "duration_minutes": 20,
        "rationale": "Small and sustainable.",
        "variant": "balanced",
        "habit_payload": {
            "name": "Morning Run",
            "category": "Fitness",
            "description": "Run for twenty minutes",
            "trigger_type": "time",
            "trigger_value": "07:00",
            "frequency_type": "custom",
            "frequency_pattern": {"days": ["monday", "wednesday", "friday"]},
            "habit_type": "binary",
            "target_value": None,
            "quantity_unit": None,
            "allows_notes": True,
            "requires_quantity": False,
            "motivation_statement": None,
        },
        "progressions": [{"week": 1, "description": "Keep it light"}],
    }
    base.update(overrides)
    return base


def test_check_streaks_resets_missed_streak_after_grace_period(client, session: Session):
    user, headers = _register_and_login(client, "streak-reset@example.com")
    habit = Habit(
        user_id=user["id"],
        name="Daily Habit",
        category="Fitness",
        description="daily",
        trigger_type="time",
        trigger_value="07:00",
        frequency_type="custom",
        frequency_pattern={"days": ALL_DAYS},
        habit_type="binary",
        current_streak=4,
        max_streak=4,
        streak_last_updated=date.today() - timedelta(days=2),
        started_at=date.today() - timedelta(days=10),
    )
    session.add(habit)
    session.commit()
    session.refresh(habit)

    response = client.post("/api/habits/check-streaks", headers=headers)

    assert response.status_code == 200
    session.refresh(habit)
    refreshed = session.get(Habit, habit.id)
    assert refreshed.current_streak == 0
    assert refreshed.max_streak == 4


def test_check_streaks_keeps_active_streak_within_grace_period(client, session: Session):
    user, headers = _register_and_login(client, "streak-safe@example.com")
    habit = Habit(
        user_id=user["id"],
        name="Daily Habit",
        category="Fitness",
        description="daily",
        trigger_type="time",
        trigger_value="07:00",
        frequency_type="custom",
        frequency_pattern={"days": ALL_DAYS},
        habit_type="binary",
        current_streak=3,
        max_streak=3,
        streak_last_updated=date.today() - timedelta(days=1),
        started_at=date.today() - timedelta(days=10),
    )
    session.add(habit)
    session.commit()
    session.refresh(habit)

    response = client.post("/api/habits/check-streaks", headers=headers)

    assert response.status_code == 200
    refreshed = session.get(Habit, habit.id)
    assert refreshed.current_streak == 3


def test_binary_analytics_success_shape(client):
    _, headers = _register_and_login(client, "binary-analytics-success@example.com")
    habit = _create_habit(client, headers, name="Binary Habit")
    complete = client.post(
        f"/api/completions/habits/{habit['id']}/complete",
        json={"completed_date": date.today().isoformat()},
        headers=headers,
    )
    assert complete.status_code == 201

    response = client.get(f"/api/habits/{habit['id']}/analytics/binary", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["habit_type"] == "binary"
    assert body["period"] == "week"
    assert len(body["bars"]) == 7


def test_tracked_analytics_success_shape(client):
    _, headers = _register_and_login(client, "tracked-analytics-success@example.com")
    habit = _create_habit(
        client,
        headers,
        name="Tracked Habit",
        habit_type="tracked",
        target_value=30.0,
        quantity_unit="minutes",
    )
    complete = client.post(
        f"/api/completions/habits/{habit['id']}/complete",
        json={"completed_date": date.today().isoformat(), "progress_value": 30.0},
        headers=headers,
    )
    assert complete.status_code == 201

    response = client.get(f"/api/habits/{habit['id']}/analytics/tracked", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["habit_type"] == "tracked"
    assert body["target_value"] == 30.0
    assert len(body["bars"]) == 7


def test_friends_inbox_outbox_and_detail_endpoints(client):
    _, sender_headers = _register_and_login(client, "outbox-user@example.com", name="Sender")
    receiver, receiver_headers = _register_and_login(client, "inbox-user@example.com", name="Receiver")

    request_response = _send_friend_request(
        client,
        sender_headers,
        receiver_id=receiver["id"],
        message="let's connect",
    )
    assert request_response.status_code == 201

    outbox = client.get("/api/friends/requests/outbox", headers=sender_headers)
    inbox = client.get("/api/friends/requests/inbox", headers=receiver_headers)
    inbox_detail = client.get("/api/friends/requests/inbox/detail", headers=receiver_headers)

    assert outbox.status_code == 200
    assert inbox.status_code == 200
    assert inbox_detail.status_code == 200
    assert outbox.json()[0]["message"] == "let's connect"
    assert inbox.json()[0]["status"] == "pending"
    assert inbox_detail.json()[0]["requester_email"] == "outbox-user@example.com"


def test_cancel_request_requires_pending_status(client):
    _, sender_headers = _register_and_login(client, "cancel-sender@example.com")
    receiver, receiver_headers = _register_and_login(client, "cancel-receiver@example.com")
    request_id = _send_friend_request(client, sender_headers, receiver_id=receiver["id"]).json()["id"]

    decline = client.post(f"/api/friends/requests/{request_id}/decline", headers=receiver_headers)
    cancel = client.post(f"/api/friends/requests/{request_id}/cancel", headers=sender_headers)

    assert decline.status_code == 200
    assert cancel.status_code == 400
    assert "pending" in cancel.json()["detail"]


def test_unfriend_removes_friend_from_lists(client):
    alice, alice_headers = _register_and_login(client, "unfriend-a@example.com", name="Alice")
    bob, bob_headers = _register_and_login(client, "unfriend-b@example.com", name="Bob")
    request_id = _send_friend_request(client, alice_headers, receiver_id=bob["id"]).json()["id"]
    accept = client.post(f"/api/friends/requests/{request_id}/accept", headers=bob_headers)
    assert accept.status_code == 200

    delete_response = client.delete(f"/api/friends/{bob['id']}", headers=alice_headers)
    friend_ids = client.get("/api/friends", headers=alice_headers)
    friend_detail = client.get("/api/friends/list/detail", headers=alice_headers)

    assert delete_response.status_code == 200
    assert friend_ids.json() == []
    assert friend_detail.json() == []


def test_community_feed_limit_validation(client):
    _, headers = _register_and_login(client, "feed-limit@example.com")

    zero = client.get("/api/community/feed", params={"limit": 0}, headers=headers)
    too_high = client.get("/api/community/feed", params={"limit": 101}, headers=headers)

    assert zero.status_code == 422
    assert too_high.status_code == 422


def test_comment_listing_and_like_unlike_round_trip(client, session: Session):
    owner, owner_headers = _register_and_login(client, "comment-owner@example.com", name="Owner")
    friend, friend_headers = _register_and_login(client, "comment-friend@example.com", name="Friend")
    request_id = _send_friend_request(client, owner_headers, receiver_id=friend["id"]).json()["id"]
    accept = client.post(f"/api/friends/requests/{request_id}/accept", headers=friend_headers)
    assert accept.status_code == 200

    post = CommunityPost(
        author_id=owner["id"],
        habit_id=None,
        post_type="goal_met",
        title="Visible Post",
        body="body",
    )
    session.add(post)
    session.commit()
    session.refresh(post)

    first_comment = client.post(
        f"/api/community/posts/{post.id}/comments",
        json={"body": "first"},
        headers=friend_headers,
    )
    second_comment = client.post(
        f"/api/community/posts/{post.id}/comments",
        json={"body": "second"},
        headers=friend_headers,
    )
    like = client.post(f"/api/community/posts/{post.id}/like", headers=friend_headers)
    unlike = client.delete(f"/api/community/posts/{post.id}/like", headers=friend_headers)
    comments = client.get(f"/api/community/posts/{post.id}/comments", headers=friend_headers)
    feed = client.get("/api/community/feed", headers=friend_headers)

    assert first_comment.status_code == 201
    assert second_comment.status_code == 201
    assert like.status_code == 201
    assert unlike.status_code == 200
    assert [item["body"] for item in comments.json()] == ["first", "second"]
    post_row = next(item for item in feed.json() if item["id"] == post.id)
    assert post_row["comment_count"] == 2
    assert post_row["like_count"] == 0
    assert post_row["viewer_has_liked"] is False


def test_debug_print_db_disabled_by_default(client):
    response = client.get("/api/debug/print-db")
    assert response.status_code == 404


def test_debug_print_db_enabled_reads_test_database(client, session: Session, engine, monkeypatch):
    _register_and_login(client, "debug-user@example.com")
    monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", "1")
    monkeypatch.setattr(debug_routes, "engine", engine)

    response = client.get("/api/debug/print-db")

    assert response.status_code == 200
    body = response.json()
    assert len(body["users"]) == 1
    assert body["habits"] == []
    assert body["completions"] == []


def test_ai_propose_habits_off_topic_returns_off_topic_action(client, monkeypatch):
    _, headers = _register_and_login(client, "ai-off-topic@example.com")

    monkey_result = SimpleNamespace(
        success=True,
        provider="mock",
        model="gpt-4o-mini",
        action="off_topic",
        assistant_message="Stay on habits",
        what_i_heard=None,
        candidates=[],
        needs_clarification=True,
    )
    monkeypatch.setattr(ai_routes, "propose_habit_candidates", lambda *args, **kwargs: monkey_result)

    response = client.post(
        "/api/ai/propose-habits",
        json={"recent_messages": [], "latest_user_message": "What's the weather like today?"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["action"] == "off_topic"


def test_ai_propose_habits_multi_habit_returns_multi_habit_action(client, monkeypatch):
    _, headers = _register_and_login(client, "ai-multi@example.com")

    monkey_result = SimpleNamespace(
        success=True,
        provider="mock",
        model="gpt-4o-mini",
        action="multi_habit",
        assistant_message="Pick one habit first",
        what_i_heard=None,
        candidates=[],
        needs_clarification=True,
    )
    monkeypatch.setattr(ai_routes, "propose_habit_candidates", lambda *args, **kwargs: monkey_result)

    response = client.post(
        "/api/ai/propose-habits",
        json={"recent_messages": [], "latest_user_message": "I want to run and also meditate every day"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["action"] == "multi_habit"


def test_ai_generate_plan_from_incomplete_draft_returns_400(client):
    _, headers = _register_and_login(client, "ai-incomplete-draft@example.com")

    response = client.post(
        "/api/ai/generate-plan-from-draft",
        json={"draft": {"goal_summary": "Run more"}},
        headers=headers,
    )

    assert response.status_code == 400
    assert "Draft is incomplete" in response.json()["detail"]


def test_ai_create_candidate_creates_habit_record(client):
    _, headers = _register_and_login(client, "ai-create-candidate@example.com")

    response = client.post(
        "/api/ai/create-candidate",
        json={"candidate": _candidate_payload()},
        headers=headers,
    )
    habits = client.get("/api/habits/", headers=headers)

    assert response.status_code == 201
    assert response.json()["habit"]["name"] == "Morning Run"
    assert len(habits.json()) == 1


def test_ai_refine_candidate_returns_candidate_payload(client):
    _, headers = _register_and_login(client, "ai-refine@example.com")

    response = client.post(
        "/api/ai/refine-candidate",
        json={
            "idea": "I want to run consistently",
            "selected_candidate": _candidate_payload(),
            "refinement": "make it easier",
            "recent_messages": [],
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "candidate" in body
    assert body["candidate"]["habit_payload"]["frequency_pattern"]


def test_ai_chat_request_validation_rejects_missing_message(client):
    _, headers = _register_and_login(client, "ai-chat-missing@example.com")

    response = client.post("/api/ai/chat", json={"draft": {}}, headers=headers)

    assert response.status_code == 422


def test_ai_generate_plan_maps_config_error_to_503(client, monkeypatch):
    _, headers = _register_and_login(client, "ai-config-error@example.com")

    def fake_generate(*args, **kwargs):
        raise AIPipelineConfigError("config broken")

    monkeypatch.setattr(ai_routes, "generate_habit_plan", fake_generate)

    response = client.post(
        "/api/ai/generate-plan",
        json={"user_goal": "Run daily", "category": "fitness", "context": None},
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "config broken"


def test_ai_intake_maps_pipeline_error_to_400(client, monkeypatch):
    _, headers = _register_and_login(client, "ai-pipeline-error@example.com")

    def fake_intake(*args, **kwargs):
        raise AIPipelineError("bad request shape")

    monkeypatch.setattr(ai_routes, "process_intake_step", fake_intake)

    response = client.post(
        "/api/ai/intake",
        json={"recent_messages": [], "current_draft": {}, "latest_user_message": "help me run"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bad request shape"


def test_ai_refine_candidate_maps_generation_error_to_502(client, monkeypatch):
    _, headers = _register_and_login(client, "ai-generation-error@example.com")

    def fake_refine(*args, **kwargs):
        raise AIPipelineGenerationError("provider failed")

    monkeypatch.setattr(ai_routes, "refine_habit_candidate", fake_refine)

    response = client.post(
        "/api/ai/refine-candidate",
        json={
            "idea": "I want to run consistently",
            "selected_candidate": _candidate_payload(),
            "refinement": "make it easier",
            "recent_messages": [],
        },
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "provider failed"


def test_ai_revise_plan_reopen_intake_response_shape(client, monkeypatch):
    _, headers = _register_and_login(client, "ai-revise-open@example.com")

    fake_result = SimpleNamespace(
        provider="mock",
        model="gpt-4o-mini",
        action="reopen_intake",
        reopen_intake=SimpleNamespace(
            assistant_message="Need more info",
            updated_draft=AIIntakeDraft(goal_summary="Run more"),
            missing_fields=["category"],
            conflict_fields=[],
            ready_for_confirmation=False,
            confirmation_summary=None,
            needs_clarification=True,
            needs_correction=False,
            intent="on_topic",
            realism_warning=None,
        ),
    )

    monkeypatch.setattr(ai_routes, "revise_habit_plan", lambda *args, **kwargs: fake_result)

    response = client.post(
        "/api/ai/revise-plan",
        json={
            "draft": {"goal_summary": "Run more"},
            "current_plan": {
                "habit_payload": _candidate_payload()["habit_payload"],
                "progressions": [{"week": 1, "description": "Keep it light"}],
            },
            "critique": "make it softer",
            "recent_messages": [],
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "reopen_intake"
    assert body["reopen_intake"]["missing_fields"] == ["category"]
