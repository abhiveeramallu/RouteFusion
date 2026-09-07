from fastapi.testclient import TestClient


def test_seed_fleet_creates_real_logins_with_distinct_recommendations(client: TestClient) -> None:
    seed_response = client.post("/demo/seed-fleet", json={"captains": 3, "rides": 5, "parcels": 5})
    assert seed_response.status_code == 200, seed_response.text
    data = seed_response.json()
    assert len(data["captains"]) == 3

    ride_ids = []
    for credential in data["captains"]:
        login_response = client.post(
            "/auth/login", json={"email": credential["email"], "password": credential["password"]}
        )
        assert login_response.status_code == 200, login_response.text
        token = login_response.json()["access_token"]

        recommendation_response = client.get(
            "/captain/recommendations", headers={"Authorization": f"Bearer {token}"}
        )
        assert recommendation_response.status_code == 200, recommendation_response.text
        ride = recommendation_response.json().get("ride")
        if ride is not None:
            ride_ids.append(ride["id"])

    assert len(set(ride_ids)) == len(ride_ids), "distinct captains must not be offered the same ride"


def test_concurrency_stress_endpoint_completes_and_resolves_to_one_winner(client: TestClient) -> None:
    # Regression test: stress_test_concurrency used to depend on
    # Depends(get_db), whose session holds SQLITE_SINGLE_WRITER_LOCK for the
    # whole request under transient sqlite mode. Since this endpoint also
    # spawns worker threads that acquire that same (non-reentrant) lock,
    # holding it for the outer request deadlocked the request against its
    # own workers — this test hangs forever if that regression reappears.
    seed_response = client.post("/demo/seed-fleet", json={"captains": 5, "rides": 3, "parcels": 3})
    assert seed_response.status_code == 200, seed_response.text

    snapshot = client.get("/snapshot").json()
    open_ride = next(ride for ride in snapshot["rides"] if ride["status"] == "open")
    open_parcel = next(parcel for parcel in snapshot["parcels"] if parcel["status"] == "open")

    stress_response = client.post(
        "/demo/stress/concurrency",
        json={"ride_id": open_ride["id"], "parcel_id": open_parcel["id"], "attempts": 5},
    )
    assert stress_response.status_code == 200, stress_response.text
    result = stress_response.json()
    assert result["succeeded"] == 1
    assert result["conflicts"] == result["attempts"] - 1
    assert result["winner_driver_id"] is not None

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200, dashboard_response.text
    concurrency = dashboard_response.json()["concurrency"]
    assert concurrency["conflicts_prevented"] >= result["conflicts"]
    assert concurrency["stress_tests_run"] >= 1
