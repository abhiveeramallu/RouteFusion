from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth import ensure_demo_user
from app.models import Driver, Parcel, Ride
from app.services.locations import resolve_location


DEMO_DRIVER_NAME = "Captain Arjun"
DEMO_DRIVER_STATUS = "available"


def ensure_demo_driver(db: Session) -> Driver:
    driver = db.scalar(select(Driver).where(Driver.display_name == DEMO_DRIVER_NAME))
    if driver:
        return driver

    user = ensure_demo_user(db)
    vit = resolve_location("VIT Vellore")
    driver = Driver(
        user_id=user.id,
        display_name=DEMO_DRIVER_NAME,
        vehicle_type="Hybrid Cab XL",
        status=DEMO_DRIVER_STATUS,
        current_lat=vit.lat + 0.003,
        current_lng=vit.lng + 0.002,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


def latest_matching_ride(db: Session) -> Ride | None:
    return db.scalar(
        select(Ride)
        .where(Ride.pickup_name == "VIT Vellore", Ride.drop_name == "CMC Hospital", Ride.status == "open")
        .order_by(desc(Ride.created_at))
    )


def latest_matching_parcel(db: Session) -> Parcel | None:
    return db.scalar(
        select(Parcel)
        .where(
            Parcel.pickup_name == "Katpadi Railway Station",
            Parcel.drop_name == "Gandhi Nagar",
            Parcel.status == "open",
        )
        .order_by(desc(Parcel.created_at))
    )


def ensure_demo_ride(db: Session) -> Ride:
    ride = latest_matching_ride(db)
    if ride:
        return ride

    user = ensure_demo_user(db)
    vit = resolve_location("VIT Vellore")
    cmc = resolve_location("CMC Hospital")
    ride = Ride(
        created_by_user_id=user.id,
        pickup_name=vit.name,
        drop_name=cmc.name,
        pickup_lat=vit.lat,
        pickup_lng=vit.lng,
        drop_lat=cmc.lat,
        drop_lng=cmc.lng,
        passenger_count=2,
        ride_type="Comfort",
    )
    db.add(ride)
    db.commit()
    db.refresh(ride)
    return ride


def ensure_demo_parcel(db: Session) -> Parcel:
    parcel = latest_matching_parcel(db)
    if parcel:
        return parcel

    user = ensure_demo_user(db)
    katpadi = resolve_location("Katpadi Railway Station")
    gandhi_nagar = resolve_location("Gandhi Nagar")
    parcel = Parcel(
        created_by_user_id=user.id,
        pickup_name=katpadi.name,
        drop_name=gandhi_nagar.name,
        pickup_lat=katpadi.lat,
        pickup_lng=katpadi.lng,
        drop_lat=gandhi_nagar.lat,
        drop_lng=gandhi_nagar.lng,
        parcel_weight=4.5,
        parcel_type="Medical Package",
        priority="High",
    )
    db.add(parcel)
    db.commit()
    db.refresh(parcel)
    return parcel


def seed_demo_scenario(db: Session) -> tuple[Driver, Ride, Parcel]:
    driver = ensure_demo_driver(db)
    ride = ensure_demo_ride(db)
    parcel = ensure_demo_parcel(db)
    return driver, ride, parcel
