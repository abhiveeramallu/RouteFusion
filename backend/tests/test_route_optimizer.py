from app.services.route_optimizer import (
    ACCEPT_BOTH_MAX_EXTRA_TIME_MIN,
    ACCEPT_BOTH_MAX_PASSENGER_DELAY_KM,
    ACCEPT_BOTH_MIN_EFFICIENCY_SCORE,
    Waypoint,
    enumerate_valid_orderings,
    optimize_route,
)


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


def test_accept_both_analysis_reflects_the_actual_decision() -> None:
    # This scenario scores well under all three ACCEPT BOTH thresholds, so
    # the recommendation should be ACCEPT BOTH and the analysis should show
    # every constraint passing.
    result = optimize_route(
        driver_location=Waypoint("Captain", 12.9722, 79.1579),
        ride_pickup=Waypoint("VIT Vellore", 12.9692, 79.1559),
        ride_drop=Waypoint("CMC Hospital", 12.9259, 79.1356),
        parcel_pickup=Waypoint("Katpadi Railway Station", 12.9682, 79.1456),
        parcel_drop=Waypoint("Gandhi Nagar", 12.9448, 79.1324),
    )

    assert result["recommendation"] == "ACCEPT BOTH"
    analysis = result["accept_both_analysis"]

    # The analysis is computed from the ACCEPT BOTH candidate directly, so it
    # must match the top-level chosen metrics when ACCEPT BOTH was chosen.
    assert analysis["efficiency_score"] == result["efficiency_score"]
    assert analysis["extra_distance"] == result["extra_distance"]
    assert analysis["extra_time"] == result["extra_time"]
    assert analysis["overlap_distance"] == result["overlap_distance"]
    assert analysis["route_sequence"] == result["optimized_route"]

    assert analysis["all_constraints_passed"] is True
    constraints_by_key = {constraint["key"]: constraint for constraint in analysis["constraints"]}
    assert constraints_by_key["efficiency_score"]["threshold"] == ACCEPT_BOTH_MIN_EFFICIENCY_SCORE
    assert constraints_by_key["extra_time"]["threshold"] == ACCEPT_BOTH_MAX_EXTRA_TIME_MIN
    assert constraints_by_key["passenger_delay"]["threshold"] == ACCEPT_BOTH_MAX_PASSENGER_DELAY_KM
    for constraint in analysis["constraints"]:
        assert constraint["passed"] is True


def test_accept_both_analysis_shows_which_constraint_failed_when_rejected() -> None:
    # Two far-apart, non-overlapping locations: bundling adds a large detour,
    # which should fail the ACCEPT BOTH constraints even though the analysis
    # is still reported (to explain why it wasn't chosen).
    result = optimize_route(
        driver_location=Waypoint("Captain", 12.9722, 79.1579),
        ride_pickup=Waypoint("VIT Vellore", 12.9692, 79.1559),
        ride_drop=Waypoint("CMC Hospital", 12.9259, 79.1356),
        parcel_pickup=Waypoint("Far Pickup", 13.5, 80.0),
        parcel_drop=Waypoint("Far Drop", 13.6, 80.2),
    )

    assert result["recommendation"] != "ACCEPT BOTH"
    analysis = result["accept_both_analysis"]
    assert analysis["all_constraints_passed"] is False
    assert any(not constraint["passed"] for constraint in analysis["constraints"])
    # The analysis must still be the ACCEPT BOTH candidate's own numbers, not
    # a copy of whatever solo/rejected option was actually chosen.
    assert analysis["efficiency_score"] < ACCEPT_BOTH_MIN_EFFICIENCY_SCORE or (
        analysis["extra_time"] > ACCEPT_BOTH_MAX_EXTRA_TIME_MIN
        or analysis["passenger_delay"] > ACCEPT_BOTH_MAX_PASSENGER_DELAY_KM
    )


def test_enumerate_valid_orderings_handles_shared_pickup_location() -> None:
    # Regression test: Waypoint equality is by (name, lat, lng), so a ride and
    # parcel sharing the exact same named pickup location (a real case with
    # this app's small set of demo locations) used to make list.index() on
    # values ambiguous — both "ride_pickup" and "parcel_pickup" resolved to
    # whichever occurrence came first, which could admit an ordering that
    # visits the real ride_pickup stop AFTER its drop. Role-index-based
    # precedence checking must still produce exactly 6 valid orderings and a
    # correct ride_drop_index in each.
    driver = Waypoint("Driver", 12.97, 79.16)
    shared_pickup = Waypoint("VIT Vellore", 12.9692, 79.1559)
    ride_drop = Waypoint("CMC Hospital", 12.9259, 79.1356)
    parcel_drop = Waypoint("Gandhi Nagar", 12.9448, 79.1324)

    orderings = enumerate_valid_orderings(driver, shared_pickup, ride_drop, shared_pickup, parcel_drop)

    assert len(orderings) == 6
    for sequence, ride_drop_index in orderings:
        # The role-index-based lookup must always resolve to the real
        # ride_drop object, regardless of the pickup-location collision.
        assert sequence[ride_drop_index] is ride_drop
