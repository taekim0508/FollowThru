from __future__ import annotations

import uuid


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_user(client, email: str | None = None, password: str = "Password123!", name: str = "Test User"):
    chosen_email = email or unique_email()
    response = client.post(
        "/api/auth/register",
        json={"email": chosen_email, "password": password, "name": name},
    )
    return response, chosen_email, password


def login_user(client, email: str, password: str):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def habit_payload(name: str = "Morning Walk", **overrides):
    payload = {
        "name": name,
        "category": "fitness",
        "description": "Walk for ten minutes",
        "trigger_type": "time",
        "trigger_value": "07:00",
        "frequency_type": "daily",
        "frequency_pattern": None,
        "requires_quantity": False,
        "quantity_unit": None,
        "allows_notes": True,
        "motivation_statement": "Stay consistent",
    }
    payload.update(overrides)
    return payload


def ai_payload(
    user_goal: str = "I want to read every day",
    category: str = "reading",
    context: dict | None = None,
):
    return {
        "user_goal": user_goal,
        "category": category,
        "context": context
        or {
            "experience_level": "beginner",
            "available_time": 15,
            "preferred_time": "morning",
        },
    }


def intake_draft(**overrides):
    draft = {
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
    }
    draft.update(overrides)
    return draft


def intake_payload(latest_user_message: str, current_draft: dict | None = None, recent_messages: list[dict] | None = None):
    return {
        "recent_messages": recent_messages or [],
        "current_draft": current_draft or intake_draft(),
        "latest_user_message": latest_user_message,
    }


def plan_snapshot_payload(**overrides):
    payload = {
        "habit_payload": habit_payload(
            name="Reading Sprint",
            category="reading",
            description="Read for ten minutes",
            trigger_value="07:00",
        ),
        "progressions": [
            {"week": 2, "description": "Read a little longer"},
            {"week": 4, "description": "Add another reading day"},
        ],
    }
    payload.update(overrides)
    return payload
