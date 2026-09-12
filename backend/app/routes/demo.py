from __future__ import annotations

import random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import register_user
from app.database import SQLITE_SINGLE_WRITER_LOCK, SessionLocal, get_db
from app.models import ConcurrencyEvent, Driver, Parcel, Ride
from app.schemas import (
    ConcurrencyStressRequest,
    ConcurrencyStressResponse,
    DemoClearResponse,
    DemoLoadResponse,
    DriverRead,
    ParcelRead,
    RideRead,
    SeedCaptainCredential,
    SeedFleetRequest,
    SeedFleetResponse,
)
from app.services.concurrency import attempt_accept
from app.services.demo_seed import ensure_named_captains, seed_demo_scenario
from app.services.locations import KNOWN_LOCATIONS
from app.services.runtime_state import reset_runtime_state

router = APIRouter(prefix="/demo", tags=["demo"])

SEED_CAPTAIN_PASSWORD = "routefusion-captain"
SEED_CAPTAIN_FIRST_NAMES = [
    "Meera", "Ravi", "Divya", "Karthik", "Ananya",
    "Suresh", "Priya", "Vikram", "Lakshmi", "Rahul",
    "Sneha", "Arvind", "Pooja", "Manoj", "Deepika",
    "Kiran", "Anitha", "Sanjay", "Nithya", "Harish",
    "Swathi", "Gopal", "Radha", "Bharath", "Kavya",
    "Naveen", "Shalini", "Mahesh", "Uma", "Prasad",
]
UNIQUE_LOCATIONS = list({location.name: location for location in KNOWN_LOCATIONS.values()}.values())
COORDINATE_JITTER_DEG = 0.02


@router.get("/load", response_model=DemoLoadResponse)
def load_demo(
    db: Session = Depends(get_db),
) -> DemoLoadResponse:
    driver, ride, parcel = seed_demo_scenario(db)
    return DemoLoadResponse(
        driver=DriverRead.model_validate(driver),
        ride=RideRead.model_validate(ride),
        parcel=ParcelRead.model_validate(parcel),
        message="Demo scenario loaded with captain, ride, and parcel requests.",
    )


@router.get("/named-captains", response_model=list[DriverRead])
def get_named_captains(
    db: Session = Depends(get_db),
) -> list[DriverRead]:
    """The fixed 3-captain roster (Arjun, Aditya, Vijay) for the Captain
    Corner captain switcher. Idempotent — creates any missing captains and
    returns all three with their current location so the frontend can show
    each one's own recommendation.
    """
    drivers = ensure_named_captains(db)
    return [DriverRead.model_validate(driver) for driver in drivers]


@router.post("/clear", response_model=DemoClearResponse)
def clear_demo(
    db: Session = Depends(get_db),
) -> DemoClearResponse:
    cleared = reset_runtime_state(db)

    return DemoClearResponse(
        cleared_rides=cleared["cleared_rides"],
        cleared_parcels=cleared["cleared_parcels"],
        cleared_decisions=cleared["cleared_decisions"],
        message="All ride, parcel, and route decision data cleared.",
    )


def _jitter(base_lat: float, base_lng: float) -> tuple[float, float]:
    return (
        base_lat + random.uniform(-COORDINATE_JITTER_DEG, COORDINATE_JITTER_DEG),
        base_lng + random.uniform(-COORDINATE_JITTER_DEG, COORDINATE_JITTER_DEG),
    )


@router.post("/seed-fleet", response_model=SeedFleetResponse)
def seed_fleet(
    payload: SeedFleetRequest,
    db: Session = Depends(get_db),
) -> SeedFleetResponse:
    """Populates the demo with several real captain accounts (not fake
    'ghost' rows) plus scattered ride/parcel requests, so the assignment
    engine has an actual multi-driver pool to solve over. Captains log in
    through the normal login form with the credentials returned here.
    """
    created_captains: list[SeedCaptainCredential] = []
    for _ in range(payload.captains):
        base_location = random.choice(UNIQUE_LOCATIONS)
        lat, lng = _jitter(base_location.lat, base_location.lng)
        suffix = uuid.uuid4().hex[:6]
        first_name = random.choice(SEED_CAPTAIN_FIRST_NAMES)
        display_name = f"Captain {first_name}"
        email = f"captain.{first_name.lower()}.{suffix}@routefusion.demo"

        user = register_user(
            db,
            email=email,
            full_name=display_name,
            password=SEED_CAPTAIN_PASSWORD,
            role="captain",
        )
        driver = user.driver
        driver.current_lat = lat
        driver.current_lng = lng
        db.add(driver)
        db.commit()

        created_captains.append(
            SeedCaptainCredential(email=email, password=SEED_CAPTAIN_PASSWORD, display_name=display_name)
        )

    for _ in range(payload.rides):
        pickup = random.choice(UNIQUE_LOCATIONS)
        drop = random.choice([location for location in UNIQUE_LOCATIONS if location.name != pickup.name])
        pickup_lat, pickup_lng = _jitter(pickup.lat, pickup.lng)
        drop_lat, drop_lng = _jitter(drop.lat, drop.lng)
        db.add(
            Ride(
                pickup_name=pickup.name,
                drop_name=drop.name,
                pickup_lat=pickup_lat,
                pickup_lng=pickup_lng,
                drop_lat=drop_lat,
                drop_lng=drop_lng,
                passenger_count=random.randint(1, 4),
                ride_type=random.choice(["Comfort", "Quick", "XL"]),
            )
        )

    for _ in range(payload.parcels):
        pickup = random.choice(UNIQUE_LOCATIONS)
        drop = random.choice([location for location in UNIQUE_LOCATIONS if location.name != pickup.name])
        pickup_lat, pickup_lng = _jitter(pickup.lat, pickup.lng)
        drop_lat, drop_lng = _jitter(drop.lat, drop.lng)
        db.add(
            Parcel(
                pickup_name=pickup.name,
                drop_name=drop.name,
                pickup_lat=pickup_lat,
                pickup_lng=pickup_lng,
                drop_lat=drop_lat,
                drop_lng=drop_lng,
                parcel_weight=round(random.uniform(0.5, 15.0), 1),
                parcel_type=random.choice(["Documents", "Medical Package", "Electronics", "Groceries"]),
                priority=random.choice(["Low", "Medium", "High", "Urgent"]),
            )
        )

    db.commit()

    return SeedFleetResponse(
        captains=created_captains,
        created_rides=payload.rides,
        created_parcels=payload.parcels,
        message=(
            f"Seeded {payload.captains} captain accounts, {payload.rides} rides, and "
            f"{payload.parcels} parcels. Log in as any captain above via the normal login form."
        ),
    )


def _run_single_accept_attempt(driver_id: int, ride_id: int, parcel_id: int) -> bool:
    # These worker threads bypass the FastAPI-managed `get_db()` dependency
    # (which serializes sqlite sessions for real requests) since they open
    # their own sessions directly, so the whole session lifecycle — creation
    # through close — needs to be inside the lock, not just the commit. A
    # session's close() checks the connection back into the pool (a rollback
    # on the shared sqlite3 connection under StaticPool), which can otherwise
    # race with the next thread's in-flight transaction on that same
    # physical connection right after this one releases the lock.
    with SQLITE_SINGLE_WRITER_LOCK:
        session = SessionLocal()
        try:
            outcome = attempt_accept(
                session, decision="accept_both", driver_id=driver_id, ride_id=ride_id, parcel_id=parcel_id
            )
            session.commit()
            return outcome.success
        finally:
            session.close()


@router.post("/stress/concurrency", response_model=ConcurrencyStressResponse)
def stress_test_concurrency(payload: ConcurrencyStressRequest) -> ConcurrencyStressResponse:
    """Fires `attempts` simultaneous accept attempts at the same ride+parcel
    pair through the exact code path a real captain's accept uses
    (attempt_accept's optimistic-locking conditional UPDATE). Exactly one
    should win; the rest come back as conflicts — this is the live,
    on-demand proof that concurrent captains can't double-book a request.

    Deliberately does NOT use the `Depends(get_db)` session: that dependency
    holds SQLITE_SINGLE_WRITER_LOCK for this request's entire lifetime under
    transient sqlite mode, and this endpoint's own worker threads need that
    same (non-reentrant) lock — holding it across the ThreadPoolExecutor
    section would deadlock the request against its own workers. Instead this
    manages short-lived sessions of its own, each briefly re-acquiring the
    lock, exactly like _run_single_accept_attempt already does.
    """
    with SQLITE_SINGLE_WRITER_LOCK:
        setup_session = SessionLocal()
        try:
            ride = setup_session.get(Ride, payload.ride_id)
            parcel = setup_session.get(Parcel, payload.parcel_id)
            if ride is None or parcel is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride or parcel not found.")
            if ride.status != "open" or parcel.status != "open":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ride and parcel must both be open to run the concurrency stress test.",
                )

            available_drivers = list(
                setup_session.scalars(select(Driver).where(Driver.status == "available").limit(payload.attempts))
            )
            if not available_drivers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No available drivers to run the stress test with. Seed a fleet first.",
                )
            # One attempt per distinct driver — reusing the same driver id
            # for multiple concurrent attempts would just be one captain
            # racing their own retries, not the "N different captains" race
            # this endpoint demonstrates.
            driver_ids = [driver.id for driver in available_drivers[: payload.attempts]]
        finally:
            setup_session.close()

    attempts = len(driver_ids)
    with ThreadPoolExecutor(max_workers=attempts) as executor:
        futures = [
            executor.submit(_run_single_accept_attempt, driver_id, payload.ride_id, payload.parcel_id)
            for driver_id in driver_ids
        ]
        results = [future.result() for future in as_completed(futures)]

    succeeded = sum(results)
    conflicts = len(results) - succeeded

    with SQLITE_SINGLE_WRITER_LOCK:
        result_session = SessionLocal()
        try:
            winner_driver_id = result_session.get(Ride, payload.ride_id).assigned_driver_id
            result_session.add(
                ConcurrencyEvent(
                    ride_id=payload.ride_id,
                    parcel_id=payload.parcel_id,
                    attempts=attempts,
                    succeeded=succeeded,
                    conflicts=conflicts,
                    winner_driver_id=winner_driver_id,
                )
            )
            result_session.commit()
        finally:
            result_session.close()

    return ConcurrencyStressResponse(
        attempts=attempts,
        succeeded=succeeded,
        conflicts=conflicts,
        winner_driver_id=winner_driver_id,
        message=(
            f"{attempts} captains raced for the same request — 1 won, "
            f"{conflicts} got a conflict. No double-booking."
        ),
    )
