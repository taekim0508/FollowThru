from __future__ import annotations

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def register_user(client, email="test@example.com", password="password123", name="Test User"):
    r = client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "name": name,
    })
    return r


def login_user(client, email="test@example.com", password="password123"):
    r = client.post("/api/auth/login", json={
        "email": email,
        "password": password,
    })
    return r


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_token(client, email="test@example.com", password="password123"):
    register_user(client, email=email, password=password)
    r = login_user(client, email=email, password=password)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def habit_payload(
    name: str = "Morning Run",
    category: str = "Fitness",
    description: str = "Go for a run",
    trigger_value: str = "07:00",
    days: list | None = None,
    habit_type: str = "binary",
    target_value: float | None = None,
    quantity_unit: str | None = None,
) -> dict:
    return {
        "name": name,
        "category": category,
        "description": description,
        "trigger_type": "time",
        "trigger_value": trigger_value,
        "frequency_type": "custom",
        "frequency_pattern": {"days": days if days is not None else ALL_DAYS},
        "habit_type": habit_type,
        "target_value": target_value,
        "quantity_unit": quantity_unit,
        "allows_notes": True,
        "requires_quantity": False,
        "motivation_statement": None,
    }
