from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import SQLITE_SINGLE_WRITER_LOCK, Base
from app.models import Driver, Parcel, Ride
from app.services.concurrency import attempt_accept


@pytest.fixture()
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return engine


def test_single_accept_claims_the_ride_and_parcel(engine) -> None:
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_local()
    driver = Driver(display_name="Driver", status="available", current_lat=12.97, current_lng=79.16)
    ride = Ride(
        pickup_name="A", drop_name="B", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, passenger_count=1, ride_type="Comfort", status="open",
    )
    parcel = Parcel(
        pickup_name="C", drop_name="D", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, parcel_weight=1.0, parcel_type="Package", priority="Low", status="open",
    )
    session.add_all([driver, ride, parcel])
    session.commit()

    outcome = attempt_accept(session, decision="accept_both", driver_id=driver.id, ride_id=ride.id, parcel_id=parcel.id)
    session.commit()

    assert outcome.success
    session.refresh(ride)
    session.refresh(parcel)
    assert ride.status == "confirmed"
    assert parcel.status == "assigned"
    assert ride.assigned_driver_id == driver.id
    assert parcel.assigned_driver_id == driver.id


def test_concurrent_accepts_resolve_to_exactly_one_winner(engine) -> None:
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    setup_session = session_local()
    drivers = [
        Driver(display_name=f"Driver {i}", status="available", current_lat=12.97, current_lng=79.16)
        for i in range(5)
    ]
    ride = Ride(
        pickup_name="A", drop_name="B", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, passenger_count=1, ride_type="Comfort", status="open",
    )
    parcel = Parcel(
        pickup_name="C", drop_name="D", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, parcel_weight=1.0, parcel_type="Package", priority="Low", status="open",
    )
    setup_session.add_all([*drivers, ride, parcel])
    setup_session.commit()
    driver_ids = [driver.id for driver in drivers]
    ride_id, parcel_id = ride.id, parcel.id
    setup_session.close()

    def worker(driver_id: int) -> bool:
        session = session_local()
        try:
            # See SQLITE_SINGLE_WRITER_LOCK: this fixture's shared in-memory
            # SQLite connection isn't safe for concurrent cursor access from
            # multiple threads, so the DB round-trip is serialized here. The
            # optimistic-locking version check still decides the one winner —
            # this lock only prevents the sqlite3 driver itself from racing.
            with SQLITE_SINGLE_WRITER_LOCK:
                outcome = attempt_accept(
                    session, decision="accept_both", driver_id=driver_id, ride_id=ride_id, parcel_id=parcel_id
                )
                session.commit()
            return outcome.success
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=len(driver_ids)) as executor:
        futures = [executor.submit(worker, driver_id) for driver_id in driver_ids]
        results = [future.result() for future in as_completed(futures)]

    assert sum(results) == 1
    assert results.count(False) == len(driver_ids) - 1

    verify_session = session_local()
    final_ride = verify_session.get(Ride, ride_id)
    final_parcel = verify_session.get(Parcel, parcel_id)
    assert final_ride.status == "confirmed"
    assert final_parcel.status == "assigned"
    assert final_ride.assigned_driver_id == final_parcel.assigned_driver_id
    assert final_ride.assigned_driver_id in driver_ids
    verify_session.close()


def test_solo_parcel_accept_beats_a_later_accept_both_and_leaves_the_ride_open(engine) -> None:
    """Two captains can independently be recommended the same parcel — one
    as part of a combined bundle, another as a standalone parcel pickup
    (see best_match_for_driver). If the solo accept lands first, the later
    accept_both must fail cleanly on the parcel step AND roll back its own
    ride claim — an "accept both" is all-or-nothing, so it must never leave
    behind a ride confirmed to a captain whose parcel half of the deal fell
    through.
    """
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_local()
    combo_driver = Driver(display_name="Combo", status="available", current_lat=12.97, current_lng=79.16)
    solo_driver = Driver(display_name="Solo", status="available", current_lat=12.97, current_lng=79.16)
    ride = Ride(
        pickup_name="A", drop_name="B", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, passenger_count=1, ride_type="Comfort", status="open",
    )
    parcel = Parcel(
        pickup_name="C", drop_name="D", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, parcel_weight=1.0, parcel_type="Package", priority="Low", status="open",
    )
    session.add_all([combo_driver, solo_driver, ride, parcel])
    session.commit()

    # The solo-parcel captain claims the parcel first.
    solo_outcome = attempt_accept(
        session, decision="accept_parcel", driver_id=solo_driver.id, ride_id=None, parcel_id=parcel.id
    )
    session.commit()
    assert solo_outcome.success

    # The combined-bundle captain's snapshot still shows the parcel as open —
    # their accept_both must fail on the parcel half.
    combo_outcome = attempt_accept(
        session, decision="accept_both", driver_id=combo_driver.id, ride_id=ride.id, parcel_id=parcel.id
    )
    session.commit()
    assert not combo_outcome.success
    assert combo_outcome.conflict_reason == "Parcel was already taken by another captain."

    session.refresh(ride)
    session.refresh(parcel)
    # The ride must NOT have been left confirmed to combo_driver — accept_both
    # is atomic, so the rolled-back parcel claim must have released the ride too.
    assert ride.status == "open"
    assert ride.assigned_driver_id is None
    assert parcel.status == "assigned_solo"
    assert parcel.assigned_driver_id == solo_driver.id


def test_accept_both_beats_a_later_solo_parcel_accept(engine) -> None:
    """The reverse ordering: the combined-bundle captain gets there first,
    so the solo-parcel captain's later attempt on the same now-claimed
    parcel must cleanly conflict rather than silently reassigning it.
    """
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_local()
    combo_driver = Driver(display_name="Combo", status="available", current_lat=12.97, current_lng=79.16)
    solo_driver = Driver(display_name="Solo", status="available", current_lat=12.97, current_lng=79.16)
    ride = Ride(
        pickup_name="A", drop_name="B", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, passenger_count=1, ride_type="Comfort", status="open",
    )
    parcel = Parcel(
        pickup_name="C", drop_name="D", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, parcel_weight=1.0, parcel_type="Package", priority="Low", status="open",
    )
    session.add_all([combo_driver, solo_driver, ride, parcel])
    session.commit()

    combo_outcome = attempt_accept(
        session, decision="accept_both", driver_id=combo_driver.id, ride_id=ride.id, parcel_id=parcel.id
    )
    session.commit()
    assert combo_outcome.success

    solo_outcome = attempt_accept(
        session, decision="accept_parcel", driver_id=solo_driver.id, ride_id=None, parcel_id=parcel.id
    )
    session.commit()
    assert not solo_outcome.success
    assert solo_outcome.conflict_reason == "Parcel was already taken by another captain."

    session.refresh(ride)
    session.refresh(parcel)
    assert ride.status == "confirmed"
    assert ride.assigned_driver_id == combo_driver.id
    assert parcel.status == "assigned"
    assert parcel.assigned_driver_id == combo_driver.id


def test_stale_reject_cannot_clobber_a_concurrent_accept(engine) -> None:
    """Regression test: attempt_accept's reject branch used to write
    ride.status = "open" unconditionally, with no version/status check —
    so a captain rejecting a now-stale recommendation could silently undo
    another captain's just-confirmed accept of the same ride+parcel pair.
    """
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_local()
    driver_a = Driver(display_name="A", status="available", current_lat=12.97, current_lng=79.16)
    driver_b = Driver(display_name="B", status="available", current_lat=12.97, current_lng=79.16)
    ride = Ride(
        pickup_name="A", drop_name="B", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, passenger_count=1, ride_type="Comfort", status="open",
    )
    parcel = Parcel(
        pickup_name="C", drop_name="D", pickup_lat=12.97, pickup_lng=79.16,
        drop_lat=12.9, drop_lng=79.2, parcel_weight=1.0, parcel_type="Package", priority="Low", status="open",
    )
    session.add_all([driver_a, driver_b, ride, parcel])
    session.commit()

    # Captain B accepts the pair first (as if A's recommendation view is now stale).
    accept_outcome = attempt_accept(
        session, decision="accept_both", driver_id=driver_b.id, ride_id=ride.id, parcel_id=parcel.id
    )
    session.commit()
    assert accept_outcome.success

    # Captain A, still holding their stale "open" view, tries to reject the same pair.
    reject_outcome = attempt_accept(
        session, decision="reject", driver_id=driver_a.id, ride_id=ride.id, parcel_id=parcel.id
    )
    session.commit()

    assert not reject_outcome.success
    session.refresh(ride)
    session.refresh(parcel)
    assert ride.status == "confirmed"
    assert parcel.status == "assigned"
    assert ride.assigned_driver_id == driver_b.id
    assert parcel.assigned_driver_id == driver_b.id
