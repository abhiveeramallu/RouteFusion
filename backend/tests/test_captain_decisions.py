import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    (
        "decision",
        "expected_mode",
        "expected_ride_status",
        "expected_parcel_status",
        "expected_ride_present",
        "expected_parcel_present",
        "expected_passenger_points",
        "expected_parcel_points",
        "expected_optimized_points",
        "expected_combined_trips",
    ),
    [
        ("accept_both", "combined", "confirmed", "assigned", True, True, 2, 2, 5, 1),
        ("accept_ride", "ride_only", "confirmed_solo", None, True, False, 2, 0, 2, 0),
        ("accept_parcel", "parcel_only", None, "assigned_solo", False, True, 0, 2, 2, 0),
    ],
)
def test_captain_can_accept_combined_or_individual_routes(
    client: TestClient,
    decision: str,
    expected_mode: str,
    expected_ride_status: str | None,
    expected_parcel_status: str | None,
    expected_ride_present: bool,
    expected_parcel_present: bool,
    expected_passenger_points: int,
    expected_parcel_points: int,
    expected_optimized_points: int,
    expected_combined_trips: int,
) -> None:
    assert client.get("/demo/load").status_code == 200

    decision_response = client.post(
        "/captain/recommendations/respond",
        json={"decision": decision},
    )
    assert decision_response.status_code == 200, decision_response.text

    recommendation_response = client.get("/captain/recommendations")
    assert recommendation_response.status_code == 200, recommendation_response.text
    recommendation = recommendation_response.json()

    assert recommendation["decision_mode"] == expected_mode
    assert recommendation["route_confirmed"] is True
    assert (recommendation["ride"] is not None) is expected_ride_present
    assert (recommendation["parcel"] is not None) is expected_parcel_present
    if expected_ride_status is not None:
        assert recommendation["ride"]["status"] == expected_ride_status
    if expected_parcel_status is not None:
        assert recommendation["parcel"]["status"] == expected_parcel_status
    assert len(recommendation["passenger_route"]) == expected_passenger_points
    assert len(recommendation["parcel_route"]) == expected_parcel_points
    assert len(recommendation["optimized_route"]) == expected_optimized_points

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200, dashboard_response.text
    assert dashboard_response.json()["metrics"]["total_combined_trips"] == expected_combined_trips


def test_rejected_pair_drops_out_of_the_recommendation_queue(client: TestClient) -> None:
    assert client.get("/demo/load").status_code == 200

    decision_response = client.post(
        "/captain/recommendations/respond",
        json={"decision": "reject"},
    )
    assert decision_response.status_code == 200, decision_response.text

    recommendation_response = client.get("/captain/recommendations")
    assert recommendation_response.status_code == 404, recommendation_response.text


def test_captain_can_accept_a_ride_without_waiting_for_a_parcel(client: TestClient) -> None:
    ride_response = client.post(
        "/ride",
        json={
            "pickup_location": "VIT Vellore",
            "drop_location": "CMC Hospital",
            "passenger_count": 2,
            "ride_type": "Comfort",
        },
    )
    assert ride_response.status_code == 201, ride_response.text

    recommendation_response = client.get("/captain/recommendations")
    assert recommendation_response.status_code == 200, recommendation_response.text
    recommendation = recommendation_response.json()

    assert recommendation["decision_mode"] == "ride_only"
    assert recommendation["route_confirmed"] is False
    assert recommendation["ride"] is not None
    assert recommendation["parcel"] is None
    assert len(recommendation["passenger_route"]) == 2
    assert recommendation["optimized_route"] == recommendation["passenger_route"]

    accept_response = client.post(
        "/captain/recommendations/respond",
        json={"decision": "accept_ride"},
    )
    assert accept_response.status_code == 200, accept_response.text

    confirmed_response = client.get("/captain/recommendations")
    assert confirmed_response.status_code == 200, confirmed_response.text
    confirmed = confirmed_response.json()

    assert confirmed["decision_mode"] == "ride_only"
    assert confirmed["route_confirmed"] is True
    assert confirmed["ride"]["status"] == "confirmed_solo"
    assert confirmed["parcel"] is None


def test_captain_can_accept_a_parcel_without_waiting_for_a_ride(client: TestClient) -> None:
    parcel_response = client.post(
        "/parcel",
        json={
            "pickup_location": "Katpadi Railway Station",
            "drop_location": "Gandhi Nagar",
            "parcel_weight": 4.5,
            "parcel_type": "Medical Package",
            "priority": "High",
        },
    )
    assert parcel_response.status_code == 201, parcel_response.text

    recommendation_response = client.get("/captain/recommendations")
    assert recommendation_response.status_code == 200, recommendation_response.text
    recommendation = recommendation_response.json()

    assert recommendation["decision_mode"] == "parcel_only"
    assert recommendation["route_confirmed"] is False
    assert recommendation["ride"] is None
    assert recommendation["parcel"] is not None
    assert len(recommendation["parcel_route"]) == 2
    assert recommendation["optimized_route"] == recommendation["parcel_route"]

    accept_response = client.post(
        "/captain/recommendations/respond",
        json={"decision": "accept_parcel"},
    )
    assert accept_response.status_code == 200, accept_response.text

    confirmed_response = client.get("/captain/recommendations")
    assert confirmed_response.status_code == 200, confirmed_response.text
    confirmed = confirmed_response.json()

    assert confirmed["decision_mode"] == "parcel_only"
    assert confirmed["route_confirmed"] is True
    assert confirmed["ride"] is None
    assert confirmed["parcel"]["status"] == "assigned_solo"


def test_completing_an_active_route_releases_the_captain_and_surfaces_the_next_queue_item(client: TestClient) -> None:
    first_ride_response = client.post(
        "/ride",
        json={
            "pickup_location": "VIT Vellore",
            "drop_location": "CMC Hospital",
            "passenger_count": 2,
            "ride_type": "Comfort",
        },
    )
    assert first_ride_response.status_code == 201, first_ride_response.text

    second_ride_response = client.post(
        "/ride",
        json={
            "pickup_location": "Katpadi Railway Station",
            "drop_location": "Gandhi Nagar",
            "passenger_count": 1,
            "ride_type": "Quick",
        },
    )
    assert second_ride_response.status_code == 201, second_ride_response.text

    accept_response = client.post(
        "/captain/recommendations/respond",
        json={"decision": "accept_ride"},
    )
    assert accept_response.status_code == 200, accept_response.text

    completion_response = client.post("/captain/recommendations/complete")
    assert completion_response.status_code == 200, completion_response.text
    assert "Collect Rs" in completion_response.json()["message"]

    next_recommendation_response = client.get("/captain/recommendations")
    assert next_recommendation_response.status_code == 200, next_recommendation_response.text
    next_recommendation = next_recommendation_response.json()

    assert next_recommendation["route_confirmed"] is False
    assert next_recommendation["decision_mode"] == "ride_only"
    assert next_recommendation["ride"]["pickup_name"] == "VIT Vellore"
    assert next_recommendation["ride"]["status"] == "open"


def test_rejecting_a_solo_ride_advances_to_the_next_ride_in_queue(client: TestClient) -> None:
    first_ride_response = client.post(
        "/ride",
        json={
            "pickup_location": "VIT Vellore",
            "drop_location": "CMC Hospital",
            "passenger_count": 2,
            "ride_type": "Comfort",
        },
    )
    assert first_ride_response.status_code == 201, first_ride_response.text

    second_ride_response = client.post(
        "/ride",
        json={
            "pickup_location": "Katpadi Railway Station",
            "drop_location": "Gandhi Nagar",
            "passenger_count": 1,
            "ride_type": "Quick",
        },
    )
    assert second_ride_response.status_code == 201, second_ride_response.text

    initial_recommendation_response = client.get("/captain/recommendations")
    assert initial_recommendation_response.status_code == 200, initial_recommendation_response.text
    initial_recommendation = initial_recommendation_response.json()
    assert initial_recommendation["ride"]["pickup_name"] == "Katpadi Railway Station"

    reject_response = client.post(
        "/captain/recommendations/respond",
        json={"decision": "reject"},
    )
    assert reject_response.status_code == 200, reject_response.text
    assert "next ride in the queue" in reject_response.json()["message"]

    next_recommendation_response = client.get("/captain/recommendations")
    assert next_recommendation_response.status_code == 200, next_recommendation_response.text
    next_recommendation = next_recommendation_response.json()

    assert next_recommendation["ride"]["pickup_name"] == "VIT Vellore"
    assert next_recommendation["ride"]["status"] == "open"
