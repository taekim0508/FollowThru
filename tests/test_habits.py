from __future__ import annotations

import pytest
from tests.helpers import get_token, auth_headers, habit_payload, ALL_DAYS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_habit(client, token, **kwargs):
    r = client.post(
        "/api/habits/",
        json=habit_payload(**kwargs),
        headers=auth_headers(token),
    )
    return r


def setup(client):
    token = get_token(client)
    return token


# ---------------------------------------------------------------------------
# POST /api/habits/
# ---------------------------------------------------------------------------

def test_create_habit_success(client):
    token = setup(client)
    r = create_habit(client, token)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Morning Run"
    assert body["category"] == "fitness"


def test_create_habit_requires_auth(client):
    r = client.post("/api/habits/", json=habit_payload())
    assert r.status_code == 401


def test_create_habit_missing_name(client):
    token = setup(client)
    payload = habit_payload()
    del payload["name"]
    r = client.post("/api/habits/", json=payload, headers=auth_headers(token))
    assert r.status_code == 422


def test_create_habit_missing_frequency_pattern(client):
    token = setup(client)
    payload = habit_payload()
    del payload["frequency_pattern"]
    r = client.post("/api/habits/", json=payload, headers=auth_headers(token))
    assert r.status_code == 422


def test_create_habit_frequency_pattern_none_rejected(client):
    token = setup(client)
    payload = habit_payload()
    payload["frequency_pattern"] = None
    r = client.post("/api/habits/", json=payload, headers=auth_headers(token))
    assert r.status_code == 422


def test_create_multiple_habits(client):
    token = setup(client)
    create_habit(client, token, name="Habit A")
    create_habit(client, token, name="Habit B")
    create_habit(client, token, name="Habit C")
    r = client.get("/api/habits/", headers=auth_headers(token))
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_create_habit_tracked_type(client):
    token = setup(client)
    r = create_habit(
        client, token,
        name="Drink Water",
        habit_type="tracked",
        target_value=8.0,
        quantity_unit="glasses",
    )
    assert r.status_code == 201
    body = r.json()
    assert body["habit_type"] == "tracked"
    assert body["target_value"] == 8.0
    assert body["quantity_unit"] == "glasses"


# ---------------------------------------------------------------------------
# GET /api/habits/
# ---------------------------------------------------------------------------

def test_list_habits_empty(client):
    token = setup(client)
    r = client.get("/api/habits/", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json() == []


def test_list_habits_returns_own_habits(client):
    t1 = get_token(client, email="alice@example.com")
    t2 = get_token(client, email="bob@example.com")
    create_habit(client, t1, name="Alice Habit")
    create_habit(client, t2, name="Bob Habit")
    r1 = client.get("/api/habits/", headers=auth_headers(t1))
    r2 = client.get("/api/habits/", headers=auth_headers(t2))
    names1 = [h["name"] for h in r1.json()]
    names2 = [h["name"] for h in r2.json()]
    assert "Alice Habit" in names1
    assert "Bob Habit" not in names1
    assert "Bob Habit" in names2


def test_list_habits_unauthenticated(client):
    r = client.get("/api/habits/")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/habits/{habit_id}
# ---------------------------------------------------------------------------

def test_get_habit_by_id(client):
    token = setup(client)
    habit_id = create_habit(client, token).json()["id"]
    r = client.get(f"/api/habits/{habit_id}", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["id"] == habit_id


def test_get_habit_not_found(client):
    token = setup(client)
    r = client.get("/api/habits/99999", headers=auth_headers(token))
    assert r.status_code == 404


def test_get_habit_other_user_forbidden(client):
    t1 = get_token(client, email="alice@example.com")
    t2 = get_token(client, email="bob@example.com")
    habit_id = create_habit(client, t1).json()["id"]
    r = client.get(f"/api/habits/{habit_id}", headers=auth_headers(t2))
    assert r.status_code in (403, 404)


# ---------------------------------------------------------------------------
# PUT /api/habits/{habit_id}
# ---------------------------------------------------------------------------

def test_update_habit(client):
    token = setup(client)
    habit_id = create_habit(client, token).json()["id"]
    r = client.put(
        f"/api/habits/{habit_id}",
        json={"name": "Evening Run", "status": "active"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Evening Run"


def test_update_habit_not_found(client):
    token = setup(client)
    r = client.put(
        "/api/habits/99999",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/habits/{habit_id}
# ---------------------------------------------------------------------------

def test_delete_habit(client):
    token = setup(client)
    habit_id = create_habit(client, token).json()["id"]
    r = client.delete(f"/api/habits/{habit_id}", headers=auth_headers(token))
    assert r.status_code == 204
    r2 = client.get(f"/api/habits/{habit_id}", headers=auth_headers(token))
    assert r2.status_code == 404


def test_delete_habit_not_found(client):
    token = setup(client)
    r = client.delete("/api/habits/99999", headers=auth_headers(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Completions
# ---------------------------------------------------------------------------

def test_complete_habit(client):
    token = setup(client)
    habit_id = create_habit(client, token).json()["id"]
    r = client.post(
        f"/api/completions/habits/{habit_id}/complete",
        json={"completed_date": "2025-01-15", "note": None},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["is_complete"] is True


def test_complete_habit_unauthenticated(client):
    r = client.post(
        "/api/completions/habits/1/complete",
        json={"completed_date": "2025-01-15", "note": None},
    )
    assert r.status_code == 401


def test_list_completions(client):
    token = setup(client)
    habit_id = create_habit(client, token).json()["id"]
    client.post(
        f"/api/completions/habits/{habit_id}/complete",
        json={"completed_date": "2025-01-15", "note": None},
        headers=auth_headers(token),
    )
    r = client.get(
        f"/api/completions/habits/{habit_id}/completions",
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_progress_update(client):
    """PATCH /progress updates an existing completion for a tracked habit."""
    from datetime import date
    token = setup(client)
    habit_id = create_habit(
        client, token,
        habit_type="tracked",
        target_value=30.0,
        quantity_unit="minutes",
    ).json()["id"]
    today = date.today().isoformat()
    # First create a completion via /complete
    cr = client.post(
        f"/api/completions/habits/{habit_id}/complete",
        json={"completed_date": today, "progress_value": 10.0},
        headers=auth_headers(token),
    )
    assert cr.status_code == 201
    # Then update the progress
    r = client.patch(
        f"/api/completions/habits/{habit_id}/progress",
        json={"completed_date": today, "progress_value": 20.0},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["progress_value"] == 20.0
    assert body["is_complete"] is False


def test_complete_tracked_at_target(client):
    """A tracked habit is auto-marked complete when progress_value >= target_value."""
    from datetime import date
    token = setup(client)
    habit_id = create_habit(
        client, token,
        habit_type="tracked",
        target_value=30.0,
        quantity_unit="minutes",
    ).json()["id"]
    today = date.today().isoformat()
    r = client.post(
        f"/api/completions/habits/{habit_id}/complete",
        json={"completed_date": today, "progress_value": 30.0},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    assert r.json()["is_complete"] is True


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------

def test_habit_has_streak_fields(client):
    token = setup(client)
    habit_id = create_habit(client, token).json()["id"]
    r = client.get(f"/api/habits/{habit_id}", headers=auth_headers(token))
    body = r.json()
    assert "current_streak" in body
    assert "max_streak" in body


def test_complete_increments_streak(client):
    token = setup(client)
    habit_id = create_habit(client, token).json()["id"]
    from datetime import date
    today = date.today().isoformat()
    r = client.post(
        f"/api/completions/habits/{habit_id}/complete",
        json={"completed_date": today, "note": None},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    assert r.json()["current_streak"] >= 1
