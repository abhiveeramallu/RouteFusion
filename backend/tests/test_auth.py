from __future__ import annotations

from fastapi.testclient import TestClient


def signup_user(client: TestClient, *, role: str, email: str) -> dict[str, object]:
    response = client.post(
        "/auth/signup",
        json={
            "full_name": f"{role.title()} User",
            "email": email,
            "password": "strong-pass-123",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_signup_refresh_logout_flow(client: TestClient) -> None:
    session = signup_user(client, role="rider", email="rider@routefusion.app")
    access_token = str(session["access_token"])
    refresh_token = str(session["refresh_token"])

    me_response = client.get("/auth/me", headers=bearer_headers(access_token))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == "rider@routefusion.app"
    assert me_response.json()["role"] == "rider"

    refreshed = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200, refreshed.text
    refreshed_body = refreshed.json()
    assert refreshed_body["access_token"] != access_token
    assert refreshed_body["refresh_token"] != refresh_token

    logout_response = client.post(
        "/auth/logout",
        headers=bearer_headers(refreshed_body["access_token"]),
        json={"refresh_token": refreshed_body["refresh_token"]},
    )
    assert logout_response.status_code == 200, logout_response.text

    revoked_refresh = client.post("/auth/refresh", json={"refresh_token": refreshed_body["refresh_token"]})
    assert revoked_refresh.status_code == 401, revoked_refresh.text
