from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Driver, DriverDecline, Parcel, Ride

AcceptDecision = Literal["accept_both", "accept_ride", "accept_parcel", "reject"]

RIDE_STATUS_COMBINED = "confirmed"
RIDE_STATUS_SOLO = "confirmed_solo"
PARCEL_STATUS_COMBINED = "assigned"
PARCEL_STATUS_SOLO = "assigned_solo"


@dataclass
class AcceptOutcome:
    success: bool
    conflict_reason: str | None = None


def _claim_ride(db: Session, ride: Ride, *, new_status: str, driver_id: int) -> bool:
    expected_version = ride.version
    result = db.execute(
        update(Ride)
        .where(Ride.id == ride.id, Ride.status == "open", Ride.version == expected_version)
        .values(status=new_status, version=Ride.version + 1, assigned_driver_id=driver_id)
    )
    if result.rowcount != 1:
        return False
    # The bulk UPDATE above bypasses the ORM identity map, so mirror the
    # change onto the already-loaded object for the rest of this request.
    ride.status = new_status
    ride.version = expected_version + 1
    ride.assigned_driver_id = driver_id
    return True


def _claim_parcel(db: Session, parcel: Parcel, *, new_status: str, driver_id: int) -> bool:
    expected_version = parcel.version
    result = db.execute(
        update(Parcel)
        .where(Parcel.id == parcel.id, Parcel.status == "open", Parcel.version == expected_version)
        .values(status=new_status, version=Parcel.version + 1, assigned_driver_id=driver_id)
    )
    if result.rowcount != 1:
        return False
    parcel.status = new_status
    parcel.version = expected_version + 1
    parcel.assigned_driver_id = driver_id
    return True


def _release_ride(db: Session, ride: Ride, *, new_status: str) -> bool:
    """Same conditional-UPDATE guard as _claim_ride, for the reject path.
    Without this, a captain rejecting a now-stale recommendation can
    unconditionally overwrite a ride another captain just accepted in the
    meantime — the exact double-booking class of bug this module exists to
    prevent, just left unguarded on this one transition.
    """
    expected_version = ride.version
    result = db.execute(
        update(Ride)
        .where(Ride.id == ride.id, Ride.status == "open", Ride.version == expected_version)
        .values(status=new_status, version=Ride.version + 1, assigned_driver_id=None)
    )
    if result.rowcount != 1:
        return False
    ride.status = new_status
    ride.version = expected_version + 1
    ride.assigned_driver_id = None
    return True


def _release_parcel(db: Session, parcel: Parcel, *, new_status: str) -> bool:
    expected_version = parcel.version
    result = db.execute(
        update(Parcel)
        .where(Parcel.id == parcel.id, Parcel.status == "open", Parcel.version == expected_version)
        .values(status=new_status, version=Parcel.version + 1, assigned_driver_id=None)
    )
    if result.rowcount != 1:
        return False
    parcel.status = new_status
    parcel.version = expected_version + 1
    parcel.assigned_driver_id = None
    return True


def attempt_accept(
    db: Session,
    *,
    decision: AcceptDecision,
    driver_id: int,
    ride_id: int | None,
    parcel_id: int | None,
) -> AcceptOutcome:
    """Optimistically claims the ride/parcel this decision needs via a
    conditional UPDATE (WHERE status='open' AND version=<snapshot>). Zero rows
    affected means another caller already claimed it since it was read —
    caller rolls back and treats this as a 409 conflict. This is what makes
    concurrent accepts from different captains resolve to exactly one winner,
    on both SQLite (this app's default transient store) and Postgres — it
    only relies on an atomic conditional UPDATE, not `SELECT ... FOR UPDATE`.
    """
    ride = db.get(Ride, ride_id) if ride_id is not None else None
    parcel = db.get(Parcel, parcel_id) if parcel_id is not None else None
    driver = db.get(Driver, driver_id)

    if decision == "accept_both":
        if ride is None or parcel is None:
            return AcceptOutcome(success=False, conflict_reason="Ride and parcel are both required.")
        if not _claim_ride(db, ride, new_status=RIDE_STATUS_COMBINED, driver_id=driver_id):
            db.rollback()
            return AcceptOutcome(success=False, conflict_reason="Ride was already taken by another captain.")
        if not _claim_parcel(db, parcel, new_status=PARCEL_STATUS_COMBINED, driver_id=driver_id):
            db.rollback()
            return AcceptOutcome(success=False, conflict_reason="Parcel was already taken by another captain.")
        if driver is not None:
            driver.status = "on_trip"

    elif decision == "accept_ride":
        if ride is None:
            return AcceptOutcome(success=False, conflict_reason="Ride is required.")
        if not _claim_ride(db, ride, new_status=RIDE_STATUS_SOLO, driver_id=driver_id):
            db.rollback()
            return AcceptOutcome(success=False, conflict_reason="Ride was already taken by another captain.")
        if driver is not None:
            driver.status = "on_trip"

    elif decision == "accept_parcel":
        if parcel is None:
            return AcceptOutcome(success=False, conflict_reason="Parcel is required.")
        if not _claim_parcel(db, parcel, new_status=PARCEL_STATUS_SOLO, driver_id=driver_id):
            db.rollback()
            return AcceptOutcome(success=False, conflict_reason="Parcel was already taken by another captain.")
        if driver is not None:
            driver.status = "on_trip"

    else:
        if ride is not None and parcel is not None:
            # "open" -> "open" looks like a no-op, but the conditional UPDATE
            # is what detects a stale reject: if either row moved on since
            # this captain last saw it, the WHERE clause matches zero rows
            # and this correctly reports a conflict instead of clobbering it.
            if not _release_ride(db, ride, new_status="open"):
                db.rollback()
                return AcceptOutcome(success=False, conflict_reason="This request was already claimed by another captain.")
            if not _release_parcel(db, parcel, new_status="open"):
                db.rollback()
                return AcceptOutcome(success=False, conflict_reason="This request was already claimed by another captain.")
        elif ride is not None:
            # A solo ride decline is this driver turning down THIS ride, not
            # the ride itself becoming invalid — reopen it so the next solve
            # can offer it to a different available captain, and record the
            # decline so this same driver isn't offered it again.
            if not _release_ride(db, ride, new_status="open"):
                db.rollback()
                return AcceptOutcome(success=False, conflict_reason="This ride was already claimed by another captain.")
            db.add(DriverDecline(driver_id=driver_id, ride_id=ride.id, parcel_id=None))
        elif parcel is not None:
            if not _release_parcel(db, parcel, new_status="open"):
                db.rollback()
                return AcceptOutcome(success=False, conflict_reason="This parcel was already claimed by another captain.")
            db.add(DriverDecline(driver_id=driver_id, ride_id=None, parcel_id=parcel.id))
        if driver is not None:
            driver.status = "available"

    return AcceptOutcome(success=True)
