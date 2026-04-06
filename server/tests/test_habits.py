from .helpers import auth_headers, habit_payload, register_user


def test_habits_crud_and_authz(client):
    first_user_response, _, _ = register_user(client, name="Owner")
    second_user_response, _, _ = register_user(client, name="Other")
    first_token = first_user_response.json()["access_token"]
    second_token = second_user_response.json()["access_token"]

    unauthorized_create = client.post("/api/habits/", json=habit_payload())
    assert unauthorized_create.status_code in (401, 403)

    create_response = client.post(
        "/api/habits/",
        json=habit_payload(name="Workout"),
        headers=auth_headers(first_token),
    )
    assert create_response.status_code == 201
    created_habit = create_response.json()
    habit_id = created_habit["id"]

    list_response = client.get("/api/habits/", headers=auth_headers(first_token))
    assert list_response.status_code == 200
    assert [habit["id"] for habit in list_response.json()] == [habit_id]

    owner_get = client.get(f"/api/habits/{habit_id}", headers=auth_headers(first_token))
    assert owner_get.status_code == 200

    other_get = client.get(f"/api/habits/{habit_id}", headers=auth_headers(second_token))
    assert other_get.status_code == 404

    update_response = client.put(
        f"/api/habits/{habit_id}",
        json={"description": "Updated description", "status": "active"},
        headers=auth_headers(first_token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Updated description"

    other_update = client.put(
        f"/api/habits/{habit_id}",
        json={"description": "Nope"},
        headers=auth_headers(second_token),
    )
    assert other_update.status_code == 404

    delete_response = client.delete(f"/api/habits/{habit_id}", headers=auth_headers(first_token))
    assert delete_response.status_code == 204

    deleted_get = client.get(f"/api/habits/{habit_id}", headers=auth_headers(first_token))
    assert deleted_get.status_code == 404


def test_complete_habit_and_list_completions(client):
    register_response, _, _ = register_user(client)
    token = register_response.json()["access_token"]

    create_response = client.post(
        "/api/habits/",
        json=habit_payload(name="Read"),
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    habit_id = create_response.json()["id"]

    completion_response = client.post(
        f"/api/completions/habits/{habit_id}/complete",
        json={"completed_date": "2026-03-20", "quantity_value": None, "note": "Done"},
        headers=auth_headers(token),
    )
    assert completion_response.status_code == 201
    assert completion_response.json()["habit_id"] == habit_id

    duplicate_completion = client.post(
        f"/api/completions/habits/{habit_id}/complete",
        json={"completed_date": "2026-03-20", "quantity_value": None, "note": None},
        headers=auth_headers(token),
    )
    assert duplicate_completion.status_code == 400

    list_response = client.get(
        f"/api/completions/habits/{habit_id}/completions",
        headers=auth_headers(token),
    )
    assert list_response.status_code == 200
    completions = list_response.json()
    assert len(completions) == 1
    assert completions[0]["completed_date"] == "2026-03-20"
