import os
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


# ----------------------------
# Utilities
# ----------------------------
def _u(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"

def assert_status(resp: httpx.Response, expected: int, msg: str = ""):
    if resp.status_code != expected:
        raise AssertionError(
            f"{msg}\nExpected {expected}, got {resp.status_code}\nBody: {resp.text}"
        )
def api_print_db(client):
    r = client.get(f"{BASE_URL}/api/debug/print-db")
    assert_status(r, 200)
    print("\n===== DATABASE STATE =====")
    print(r.json())

def pretty(resp: httpx.Response) -> str:
    return f"{resp.status_code} {resp.text}"

def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

def is_json(resp: httpx.Response) -> bool:
    return resp.headers.get("content-type", "").lower().startswith("application/json")

def j(resp: httpx.Response) -> Any:
    return resp.json() if is_json(resp) else None

def server_is_up(client: httpx.Client) -> bool:
    # Try a couple common endpoints without assuming you have a health route.
    for path in ("/openapi.json", "/docs", "/"):
        try:
            r = client.get(f"{BASE_URL}{path}")
            if r.status_code in (200, 302):
                return True
        except Exception:
            pass
    return False


# ----------------------------
# Optional: server-side reset (if you add /api/test/reset)
# ----------------------------
def try_server_reset(client: httpx.Client) -> bool:
    try:
        r = client.post(f"{BASE_URL}/api/test/reset", timeout=10)
        if r.status_code == 200:
            return True
        return False
    except Exception:
        return False


# ----------------------------
# API helpers
# ----------------------------
def api_register(client: httpx.Client, email: str, password: str, name: Optional[str] = None) -> Tuple[httpx.Response, Any]:
    r = client.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": name},
    )
    return r, j(r)

def api_login(client: httpx.Client, email: str, password: str) -> Tuple[httpx.Response, Any]:
    r = client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
    )
    return r, j(r)

def api_logout(client: httpx.Client) -> httpx.Response:
    return client.post(f"{BASE_URL}/api/auth/logout")

def api_create_habit(client: httpx.Client, token: str, name: str) -> httpx.Response:
    payload = {
        "name": name,
        "category": "fitness",
        "description": "test habit",
        "trigger_type": "time",
        "trigger_value": "07:00",
        "frequency_type": "daily",
        "frequency_pattern": None,
        "requires_quantity": False,
        "quantity_unit": None,
        "allows_notes": True,
        "motivation_statement": None,
    }
    return client.post(f"{BASE_URL}/api/habits/", json=payload, headers=auth_headers(token))

def api_list_habits(client: httpx.Client, token: str) -> httpx.Response:
    return client.get(f"{BASE_URL}/api/habits/", headers=auth_headers(token))

def api_get_habit(client: httpx.Client, token: str, habit_id: int) -> httpx.Response:
    return client.get(f"{BASE_URL}/api/habits/{habit_id}", headers=auth_headers(token))

def api_update_habit(client: httpx.Client, token: str, habit_id: int, patch: Dict[str, Any]) -> httpx.Response:
    return client.put(f"{BASE_URL}/api/habits/{habit_id}", json=patch, headers=auth_headers(token))

def api_delete_habit(client: httpx.Client, token: str, habit_id: int) -> httpx.Response:
    return client.delete(f"{BASE_URL}/api/habits/{habit_id}", headers=auth_headers(token))

def api_complete_habit(client: httpx.Client, token: str, habit_id: int, d: str) -> httpx.Response:
    return client.post(
        f"{BASE_URL}/api/completions/habits/{habit_id}/complete",
        json={"completed_date": d, "quantity_value": None, "note": None},
        headers=auth_headers(token),
    )

def api_list_completions(client: httpx.Client, token: str, habit_id: int) -> httpx.Response:
    return client.get(
        f"{BASE_URL}/api/completions/habits/{habit_id}/completions",
        headers=auth_headers(token),
    )

def api_send_friend_request(client: httpx.Client, token: str, receiver_id: int, message: Optional[str] = None) -> httpx.Response:
    params = {"receiver_id": receiver_id}
    if message is not None:
        params["message"] = message
    return client.post(
        f"{BASE_URL}/api/friends/requests",
        params=params,
        headers=auth_headers(token),
    )

def api_inbox(client: httpx.Client, token: str) -> httpx.Response:
    return client.get(f"{BASE_URL}/api/friends/requests/inbox", headers=auth_headers(token))

def api_outbox(client: httpx.Client, token: str) -> httpx.Response:
    return client.get(f"{BASE_URL}/api/friends/requests/outbox", headers=auth_headers(token))

def api_accept_request(client: httpx.Client, token: str, request_id: int) -> httpx.Response:
    return client.post(f"{BASE_URL}/api/friends/requests/{request_id}/accept", headers=auth_headers(token))

def api_decline_request(client: httpx.Client, token: str, request_id: int) -> httpx.Response:
    return client.post(f"{BASE_URL}/api/friends/requests/{request_id}/decline", headers=auth_headers(token))

def api_cancel_request(client: httpx.Client, token: str, request_id: int) -> httpx.Response:
    return client.post(f"{BASE_URL}/api/friends/requests/{request_id}/cancel", headers=auth_headers(token))

def api_list_friends(client: httpx.Client, token: str) -> httpx.Response:
    return client.get(f"{BASE_URL}/api/friends", headers=auth_headers(token))

def api_unfriend(client: httpx.Client, token: str, friend_id: int) -> httpx.Response:
    return client.delete(f"{BASE_URL}/api/friends/{friend_id}", headers=auth_headers(token))


# ----------------------------
# Tests
# ----------------------------
def test_auth_register_login_logout(client: httpx.Client):
    email = f"{_u('user')}@example.com"
    password = "Password123!"
    name = "Test User"

    r, data = api_register(client, email, password, name)
    assert_status(r, 201, "Register failed")
    assert data and "access_token" in data, "Register did not return access_token"
    assert data.get("user", {}).get("id"), "Register did not return user.id"

    # Duplicate -> 409
    r2, _ = api_register(client, email, password, name)
    assert_status(r2, 409, "Expected 409 on duplicate register")

    # Login ok
    r3, data3 = api_login(client, email, password)
    assert_status(r3, 200, "Login failed")
    assert data3 and data3.get("access_token"), "Login returned empty token"

    # Wrong pw -> 401
    r4, _ = api_login(client, email, "wrongpass")
    assert_status(r4, 401, "Expected 401 on wrong password")

    # Logout -> 200
    r5 = api_logout(client)
    assert_status(r5, 200, "Logout failed")

    print("✅ test_auth_register_login_logout passed")


def test_habits_crud_and_authz(client: httpx.Client):
    p = "Password123!"
    e1 = f"{_u('u1')}@example.com"
    e2 = f"{_u('u2')}@example.com"

    r1, d1 = api_register(client, e1, p, "U1")
    assert_status(r1, 201)
    t1 = d1["access_token"]

    r2, d2 = api_register(client, e2, p, "U2")
    assert_status(r2, 201)
    t2 = d2["access_token"]

    # Unauthorized create habit -> 401/403
    payload = {
        "name": "X",
        "category": "fitness",
        "description": "x",
        "trigger_type": "time",
        "trigger_value": "07:00",
        "frequency_type": "daily",
        "frequency_pattern": None,
        "requires_quantity": False,
        "quantity_unit": None,
        "allows_notes": True,
        "motivation_statement": None,
    }
    r0 = client.post(f"{BASE_URL}/api/habits/", json=payload)
    if r0.status_code == 200:
        raise AssertionError("Expected auth protection on /api/habits/ but got 200")
    if r0.status_code not in (401, 403):
        raise AssertionError(f"Expected 401/403 for unauthorized, got {pretty(r0)}")

    # Create habit (user1)
    rh = api_create_habit(client, t1, "Workout")
    assert_status(rh, 201, "Create habit failed")
    hid = rh.json()["id"]

    # List habits (user1) includes it
    rl = api_list_habits(client, t1)
    assert_status(rl, 200, "List habits failed")
    assert any(h["id"] == hid for h in rl.json()), "Created habit not in list"

    # Get habit (user1) ok
    rg = api_get_habit(client, t1, hid)
    assert_status(rg, 200, "Get habit failed")

    # Get habit (user2) -> 404
    rg2 = api_get_habit(client, t2, hid)
    assert_status(rg2, 404, "Expected 404 when other user accesses habit")

    # Update habit (user1)
    ru = api_update_habit(client, t1, hid, {"description": "updated", "status": "active"})
    assert_status(ru, 200, "Update habit failed")
    assert ru.json()["description"] == "updated"

    # Update habit (user2) -> 404
    ru2 = api_update_habit(client, t2, hid, {"description": "hacked"})
    assert_status(ru2, 404, "Expected 404 when other user updates habit")

    # Delete habit (user1) -> 204
    rd = api_delete_habit(client, t1, hid)
    assert_status(rd, 204, "Delete habit failed")

    print("✅ test_habits_crud_and_authz passed")


def test_completions_happy_and_edges(client: httpx.Client):
    e = f"{_u('u')}@example.com"
    p = "Password123!"
    r, d = api_register(client, e, p, "User")
    assert_status(r, 201)
    token = d["access_token"]

    # Create habit
    rh = api_create_habit(client, token, "Read")
    assert_status(rh, 201)
    hid = rh.json()["id"]

    # Complete once
    date_str = "2026-02-22"
    rc = api_complete_habit(client, token, hid, date_str)
    assert_status(rc, 201, "Complete habit failed")
    comp_id = rc.json().get("id")
    assert comp_id, "Completion missing id (DB write failed?)"

    # Complete same date again -> 400
    rc2 = api_complete_habit(client, token, hid, date_str)
    assert_status(rc2, 400, "Expected 400 on duplicate completion date")

    # List completions -> should include exactly 1
    rl = api_list_completions(client, token, hid)
    assert_status(rl, 200, "List completions failed")
    assert len(rl.json()) == 1, f"Expected 1 completion, got {len(rl.json())}"

    # Complete non-existent habit -> 404
    rc3 = api_complete_habit(client, token, 999999, date_str)
    assert_status(rc3, 404, "Expected 404 completing non-existent habit")

    print("✅ test_completions_happy_and_edges passed")


def test_friends_flow_and_edges(client: httpx.Client):
    p = "Password123!"
    e1 = f"{_u('alice')}@example.com"
    e2 = f"{_u('bob')}@example.com"

    a_r, a = api_register(client, e1, p, "Alice")
    b_r, b = api_register(client, e2, p, "Bob")
    assert_status(a_r, 201)
    assert_status(b_r, 201)

    alice_id = a["user"]["id"]
    bob_id = b["user"]["id"]
    alice_token = a["access_token"]
    bob_token = b["access_token"]

    # Self-request -> 400
    self_req = api_send_friend_request(client, alice_token, alice_id)
    assert_status(self_req, 400, "Expected 400 on self friend request")

    # Send request Alice->Bob
    r1 = api_send_friend_request(client, alice_token, bob_id, "yo")
    assert_status(r1, 201, f"Send request failed: {pretty(r1)}")
    req_id = r1.json()["id"]

    # Duplicate pending -> 409
    rdup = api_send_friend_request(client, alice_token, bob_id)
    assert_status(rdup, 409, "Expected 409 on duplicate pending request")

    # Bob inbox has it
    inbox = api_inbox(client, bob_token)
    assert_status(inbox, 200)
    assert any(fr["id"] == req_id for fr in inbox.json()), "Request not found in inbox"

    # Alice outbox has it
    outbox = api_outbox(client, alice_token)
    assert_status(outbox, 200)
    assert any(fr["id"] == req_id for fr in outbox.json()), "Request not found in outbox"

    # Requester tries accept -> 404
    bad_accept = api_accept_request(client, alice_token, req_id)
    assert_status(bad_accept, 404, "Expected 404 when requester tries to accept")

    # Bob accepts -> 200
    ok_accept = api_accept_request(client, bob_token, req_id)
    assert_status(ok_accept, 200, "Accept failed")

    # Accept again -> 400
    again = api_accept_request(client, bob_token, req_id)
    assert_status(again, 400, "Expected 400 on accepting already processed request")

    # List friends returns ids
    fl_a = api_list_friends(client, alice_token)
    fl_b = api_list_friends(client, bob_token)
    assert_status(fl_a, 200)
    assert_status(fl_b, 200)
    assert bob_id in fl_a.json(), "Bob missing from Alice friends list"
    assert alice_id in fl_b.json(), "Alice missing from Bob friends list"

    # Unfriend -> 200
    uf = api_unfriend(client, alice_token, bob_id)
    assert_status(uf, 200, "Unfriend failed")

    # Unfriend again -> 404
    uf2 = api_unfriend(client, alice_token, bob_id)
    assert_status(uf2, 404, "Expected 404 when unfriending non-friend")

    print("✅ test_friends_flow_and_edges passed")


# ----------------------------
# Runner
# ----------------------------
if __name__ == "__main__":
    with httpx.Client(timeout=10) as client:
        if not server_is_up(client):
            raise SystemExit(
                f"Server not reachable at {BASE_URL}. Start it (uvicorn app.main:app --reload) then rerun."
            )

        # Optional reset: if you implement /api/test/reset and enable it, we start clean.
        reset_ok = try_server_reset(client)
        if reset_ok:
            print("🧼 Server DB reset via /api/test/reset")

        test_auth_register_login_logout(client)
        test_habits_crud_and_authz(client)
        test_completions_happy_and_edges(client)

        # Only run if you wired /api/friends
        try:
            test_friends_flow_and_edges(client)
        except AssertionError as e:
            # If friends routes aren't wired yet, you'll likely get 404s; surface cleanly.
            raise

        print("\n🎉 All selected tests passed")