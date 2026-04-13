from __future__ import annotations

import pytest
from tests.helpers import register_user, login_user, auth_headers, get_token


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_success(client):
    r = register_user(client)
    assert r.status_code == 201
    body = r.json()
    assert "access_token" in body
    assert body["user"]["email"] == "test@example.com"


def test_login_token_in_response(client):
    register_user(client)
    r = login_user(client)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_register_duplicate_email(client):
    register_user(client)
    r = register_user(client)
    assert r.status_code == 409


def test_register_missing_email(client):
    r = client.post("/api/auth/register", json={
        "password": "password123",
        "name": "Test",
    })
    assert r.status_code == 422


def test_register_missing_password(client):
    r = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "name": "Test",
    })
    assert r.status_code == 422


def test_register_short_password(client):
    r = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "abc",
        "name": "Test",
    })
    assert r.status_code == 400


def test_register_invalid_email(client):
    r = client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "password123",
        "name": "Test",
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_success(client):
    register_user(client)
    r = login_user(client)
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["email"] == "test@example.com"


def test_login_wrong_password(client):
    register_user(client)
    r = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword",
    })
    assert r.status_code in (401, 403)


def test_login_unknown_email(client):
    r = login_user(client, email="nobody@example.com")
    assert r.status_code in (401, 403)


def test_login_missing_fields(client):
    r = client.post("/api/auth/login", json={"email": "test@example.com"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

def test_get_me_authenticated(client):
    token = get_token(client)
    r = client.get("/api/auth/me", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


def test_get_me_unauthenticated(client):
    r = client.get("/api/auth/me")
    assert r.status_code in (401, 403)


def test_get_me_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer badtoken"})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /me
# ---------------------------------------------------------------------------

def test_update_me(client):
    token = get_token(client)
    r = client.patch(
        "/api/auth/me",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


# ---------------------------------------------------------------------------
# Multiple users are independent
# ---------------------------------------------------------------------------

def test_multiple_users(client):
    t1 = get_token(client, email="alice@example.com", password="password123")
    t2 = get_token(client, email="bob@example.com", password="password123")
    r1 = client.get("/api/auth/me", headers=auth_headers(t1))
    r2 = client.get("/api/auth/me", headers=auth_headers(t2))
    assert r1.json()["email"] == "alice@example.com"
    assert r2.json()["email"] == "bob@example.com"


# ---------------------------------------------------------------------------
# POST /delete-account
# ---------------------------------------------------------------------------


def test_delete_account_success(client):
    register_user(client)
    token = get_token(client)
    r = client.post(
        "/api/auth/delete-account",
        json={"password": "password123"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json().get("message") == "Account deleted"
    # token is invalid — user row gone
    r2 = client.get("/api/auth/me", headers=auth_headers(token))
    assert r2.status_code in (401, 403)
    # cannot log in again with same credentials
    r3 = login_user(client)
    assert r3.status_code in (401, 403)


def test_delete_account_wrong_password(client):
    register_user(client)
    token = get_token(client)
    r = client.post(
        "/api/auth/delete-account",
        json={"password": "wrongpassword"},
        headers=auth_headers(token),
    )
    assert r.status_code == 401
    r2 = client.get("/api/auth/me", headers=auth_headers(token))
    assert r2.status_code == 200


def test_delete_account_requires_auth(client):
    r = client.post("/api/auth/delete-account", json={"password": "password123"})
    assert r.status_code in (401, 403)
