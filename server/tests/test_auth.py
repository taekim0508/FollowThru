from .helpers import auth_headers, login_user, register_user, unique_email


def test_register_login_get_me_and_update_account(client):
    register_response, email, password = register_user(client, name="Original Name")
    assert register_response.status_code == 201

    body = register_response.json()
    assert body["access_token"]
    assert body["user"]["email"] == email
    assert body["user"]["name"] == "Original Name"

    token = body["access_token"]
    me_response = client.get("/api/auth/me", headers=auth_headers(token))
    assert me_response.status_code == 200
    assert me_response.json()["email"] == email

    update_response = client.patch(
        "/api/auth/me",
        json={
            "name": "Updated Name",
            "current_password": password,
            "new_password": "NewPassword123!",
        },
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Name"

    old_login = login_user(client, email, password)
    assert old_login.status_code == 401

    new_login = login_user(client, email, "NewPassword123!")
    assert new_login.status_code == 200
    assert new_login.json()["user"]["name"] == "Updated Name"


def test_auth_rejects_duplicate_registration_and_requires_auth_for_me(client):
    email = unique_email("duplicate")

    first_response, _, _ = register_user(client, email=email)
    assert first_response.status_code == 201

    duplicate_response, _, _ = register_user(client, email=email)
    assert duplicate_response.status_code == 409

    me_response = client.get("/api/auth/me")
    assert me_response.status_code in (401, 403)
