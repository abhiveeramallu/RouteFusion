from app.services.route_optimizer import Waypoint, optimize_route


def test_optimizer_returns_bounded_metrics() -> None:
    result = optimize_route(
        driver_location=Waypoint("Captain", 12.9722, 79.1579),
        ride_pickup=Waypoint("VIT Vellore", 12.9692, 79.1559),
        ride_drop=Waypoint("CMC Hospital", 12.9259, 79.1356),
        parcel_pickup=Waypoint("Katpadi Railway Station", 12.9682, 79.1456),
        parcel_drop=Waypoint("Gandhi Nagar", 12.9448, 79.1324),
    )

    assert 0 <= result["efficiency_score"] <= 100
    assert result["recommendation"] in {
        "ACCEPT BOTH",
        "PASSENGER FIRST",
        "PARCEL FIRST",
        "REJECT COMBINATION",
    }
    assert result["optimized_route"]
