import random

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Driver, DriverDecline, Parcel, Ride, RouteDecision
from app.services.assignment_engine import best_match_for_driver, run_assignment


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


def make_driver(session, *, lat, lng, name="Driver") -> Driver:
    driver = Driver(display_name=name, status="available", current_lat=lat, current_lng=lng)
    session.add(driver)
    session.commit()
    session.refresh(driver)
    return driver


def make_ride(session, *, pickup_lat, pickup_lng, drop_lat=12.9, drop_lng=79.2) -> Ride:
    ride = Ride(
        pickup_name="Pickup",
        drop_name="Drop",
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        drop_lat=drop_lat,
        drop_lng=drop_lng,
        passenger_count=1,
        ride_type="Comfort",
        status="open",
    )
    session.add(ride)
    session.commit()
    session.refresh(ride)
    return ride


def make_parcel(session, *, pickup_lat, pickup_lng, drop_lat=12.9, drop_lng=79.2) -> Parcel:
    parcel = Parcel(
        pickup_name="Parcel Pickup",
        drop_name="Parcel Drop",
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        drop_lat=drop_lat,
        drop_lng=drop_lng,
        parcel_weight=2.0,
        parcel_type="Package",
        priority="Low",
        status="open",
    )
    session.add(parcel)
    session.commit()
    session.refresh(parcel)
    return parcel


def test_two_drivers_get_their_own_nearest_ride(db_session) -> None:
    driver_north = make_driver(db_session, lat=13.05, lng=79.15, name="North Driver")
    driver_south = make_driver(db_session, lat=12.85, lng=79.15, name="South Driver")

    ride_north = make_ride(db_session, pickup_lat=13.06, pickup_lng=79.15)
    ride_south = make_ride(db_session, pickup_lat=12.86, pickup_lng=79.15)

    result = run_assignment(db_session)

    assert result.by_driver_id[driver_north.id].ride.id == ride_north.id
    assert result.by_driver_id[driver_south.id].ride.id == ride_south.id
    assert result.stats.drivers_considered == 2
    assert result.stats.rides_considered == 2


def test_rejected_pair_is_not_reassigned(db_session) -> None:
    driver = make_driver(db_session, lat=12.97, lng=79.16)
    ride = make_ride(db_session, pickup_lat=12.97, pickup_lng=79.16)
    parcel = make_parcel(db_session, pickup_lat=12.971, pickup_lng=79.161)

    db_session.add(
        RouteDecision(
            driver_id=driver.id,
            ride_id=ride.id,
            parcel_id=parcel.id,
            efficiency_score=0.0,
            extra_distance=0.0,
            extra_time=0.0,
            overlap_distance=0.0,
            recommendation="reject",
            accepted=False,
        )
    )
    db_session.commit()

    result = run_assignment(db_session)

    assignment = result.by_driver_id[driver.id]
    assert assignment.ride.id == ride.id
    assert assignment.parcel is None


def test_declined_ride_flows_to_the_next_available_driver(db_session) -> None:
    near_driver = make_driver(db_session, lat=12.9692, lng=79.1559, name="Near")
    far_driver = make_driver(db_session, lat=12.90, lng=79.10, name="Far")
    ride = make_ride(db_session, pickup_lat=12.9692, pickup_lng=79.1559)

    # Nearer driver wins the fresh solve.
    result = run_assignment(db_session)
    assert result.by_driver_id[near_driver.id].ride.id == ride.id
    assert result.by_driver_id[far_driver.id].ride is None

    # That driver declines it solo — it must stay open for someone else,
    # not disappear, and must not be re-offered to the driver who declined.
    db_session.add(DriverDecline(driver_id=near_driver.id, ride_id=ride.id, parcel_id=None))
    db_session.commit()

    result = run_assignment(db_session)
    assert result.by_driver_id[near_driver.id].ride is None
    assert result.by_driver_id[far_driver.id].ride.id == ride.id


def test_declined_parcel_flows_to_the_next_available_driver(db_session) -> None:
    near_driver = make_driver(db_session, lat=12.9692, lng=79.1559, name="Near")
    far_driver = make_driver(db_session, lat=12.90, lng=79.10, name="Far")
    parcel = make_parcel(db_session, pickup_lat=12.9692, pickup_lng=79.1559)

    result = run_assignment(db_session)
    assert result.by_driver_id[near_driver.id].parcel.id == parcel.id
    assert result.by_driver_id[far_driver.id].parcel is None

    db_session.add(DriverDecline(driver_id=near_driver.id, ride_id=None, parcel_id=parcel.id))
    db_session.commit()

    result = run_assignment(db_session)
    assert result.by_driver_id[near_driver.id].parcel is None
    assert result.by_driver_id[far_driver.id].parcel.id == parcel.id


def test_suitability_cap_excludes_a_driver_too_far_from_the_pickup(db_session) -> None:
    near_driver = make_driver(db_session, lat=12.9692, lng=79.1559, name="Near")
    far_driver = make_driver(db_session, lat=12.80, lng=79.00, name="Far")  # ~25 km away
    ride = make_ride(db_session, pickup_lat=12.9692, pickup_lng=79.1559)

    result = run_assignment(db_session)

    assert result.by_driver_id[near_driver.id].ride.id == ride.id
    assert result.by_driver_id[far_driver.id].ride is None


def test_ride_stays_unmatched_when_no_driver_is_within_reach(db_session) -> None:
    far_driver = make_driver(db_session, lat=12.80, lng=79.00)  # ~25 km from the pickup
    ride = make_ride(db_session, pickup_lat=12.9692, pickup_lng=79.1559)

    result = run_assignment(db_session)

    assert result.by_driver_id[far_driver.id].ride is None


def test_two_nearby_drivers_can_both_be_recommended_the_same_ride(db_session) -> None:
    # This is the actual fix: run_assignment's fleet-wide Hungarian solve is
    # exclusive (one driver per ride) by design, but a captain's own
    # recommendation must NOT be read off that shared matching — otherwise a
    # ride is only ever visible to whichever single driver the global solve
    # happened to pick, even when another driver is equally close and free.
    # best_match_for_driver evaluates each driver independently, so both
    # should legitimately see the same ride as their own best option.
    first_driver = make_driver(db_session, lat=12.9692, lng=79.1559, name="First")
    second_driver = make_driver(db_session, lat=12.9695, lng=79.1561, name="Second")
    ride = make_ride(db_session, pickup_lat=12.9692, pickup_lng=79.1559)

    first_match = best_match_for_driver(db_session, first_driver)
    second_match = best_match_for_driver(db_session, second_driver)

    assert first_match.ride is not None and first_match.ride.id == ride.id
    assert second_match.ride is not None and second_match.ride.id == ride.id


def test_best_match_for_driver_respects_the_suitability_cap(db_session) -> None:
    far_driver = make_driver(db_session, lat=12.80, lng=79.00)  # ~25 km away
    make_ride(db_session, pickup_lat=12.9692, pickup_lng=79.1559)

    match = best_match_for_driver(db_session, far_driver)

    assert match.ride is None


def test_best_match_for_driver_excludes_a_ride_this_driver_declined(db_session) -> None:
    driver = make_driver(db_session, lat=12.9692, lng=79.1559)
    ride = make_ride(db_session, pickup_lat=12.9692, pickup_lng=79.1559)

    match_before = best_match_for_driver(db_session, driver)
    assert match_before.ride is not None and match_before.ride.id == ride.id

    db_session.add(DriverDecline(driver_id=driver.id, ride_id=ride.id, parcel_id=None))
    db_session.commit()

    match_after = best_match_for_driver(db_session, driver)
    assert match_after.ride is None


def test_driver_with_no_ride_gets_standalone_parcel(db_session) -> None:
    driver = make_driver(db_session, lat=12.97, lng=79.16)
    parcel = make_parcel(db_session, pickup_lat=12.971, pickup_lng=79.161)

    result = run_assignment(db_session)

    assignment = result.by_driver_id[driver.id]
    assert assignment.ride is None
    assert assignment.parcel.id == parcel.id


def test_optimal_never_underperforms_greedy_across_random_scenarios(db_session) -> None:
    # Regression test: an earlier version compared Hungarian's total cost
    # directly against a driver-order greedy baseline. Hungarian can match
    # MORE drivers than that greedy pass (via an augmenting path greedy
    # can't find), which made "optimal" look more expensive purely because
    # it covered more drivers — not because the assignment was worse. The
    # fix: use an edge-sorted greedy baseline for a fair comparison, and
    # only compare cost when both matched the same number of pairs.
    random.seed(0)
    for trial in range(25):
        for driver_index in range(random.randint(1, 10)):
            make_driver(
                db_session,
                lat=12.9 + random.uniform(-0.05, 0.05),
                lng=79.15 + random.uniform(-0.05, 0.05),
                name=f"trial{trial}-driver{driver_index}",
            )
        for ride_index in range(random.randint(1, 10)):
            make_ride(
                db_session,
                pickup_lat=12.9 + random.uniform(-0.05, 0.05),
                pickup_lng=79.15 + random.uniform(-0.05, 0.05),
            )

        stats = run_assignment(db_session).stats
        assert stats.optimal_matched_count >= stats.greedy_matched_count
        if stats.optimal_matched_count == stats.greedy_matched_count:
            assert stats.optimal_cost <= stats.greedy_cost + 1e-6

        # Reset for the next trial's fresh random scenario.
        db_session.query(Driver).delete()
        db_session.query(Ride).delete()
        db_session.commit()
