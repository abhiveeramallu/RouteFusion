from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Driver, Parcel, Ride, RouteDecision
from app.schemas import MessageResponse, RideCreate, RideRead
from app.services.locations import resolve_location_input

router = APIRouter(tags=["rides"])

ACCEPTED_RIDE_STATUSES = {"confirmed", "confirmed_solo"}
CLOSED_RIDE_STATUSES = {"completed", "cancelled", "rejected"}


def latest_accepted_ride_decision(db: Session, ride_id: int) -> RouteDecision | None:
    return db.scalar(
        select(RouteDecision)
        .where(RouteDecision.ride_id == ride_id, RouteDecision.accepted.is_(True))
        .order_by(desc(RouteDecision.created_at))
    )


@router.post("/ride", response_model=RideRead, status_code=status.HTTP_201_CREATED)
def create_ride(
    payload: RideCreate,
    db: Session = Depends(get_db),
) -> Ride:
    try:
        pickup = resolve_location_input(
            payload.pickup_location,
            payload.pickup_point.lat if payload.pickup_point else None,
            payload.pickup_point.lng if payload.pickup_point else None,
        )
        drop = resolve_location_input(
            payload.drop_location,
            payload.drop_point.lat if payload.drop_point else None,
            payload.drop_point.lng if payload.drop_point else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ride = Ride(
        pickup_name=pickup.name,
        drop_name=drop.name,
        pickup_lat=pickup.lat,
        pickup_lng=pickup.lng,
        drop_lat=drop.lat,
        drop_lng=drop.lng,
        passenger_count=payload.passenger_count,
        ride_type=payload.ride_type,
    )
    db.add(ride)
    db.commit()
    db.refresh(ride)
    return ride


@router.get("/ride", response_model=list[RideRead])
def list_rides(
    db: Session = Depends(get_db),
) -> list[Ride]:
    return list(db.scalars(select(Ride).order_by(desc(Ride.created_at)).limit(10)))


@router.delete("/ride/{ride_id}", response_model=MessageResponse)
def cancel_ride(
    ride_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride request not found.")

    if ride.status in CLOSED_RIDE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ride can no longer be cancelled.",
        )

    decision = latest_accepted_ride_decision(db, ride.id)
    driver = db.get(Driver, decision.driver_id) if decision is not None else None
    linked_parcel = db.get(Parcel, decision.parcel_id) if decision is not None else None
    was_accepted = ride.status in ACCEPTED_RIDE_STATUSES

    if ride.status == "confirmed" and linked_parcel is not None and linked_parcel.status == "assigned":
        linked_parcel.status = "open"

    ride.status = "cancelled"

    if was_accepted and driver is not None:
        driver.status = "available"

    db.commit()

    if was_accepted:
        return MessageResponse(
            message="Ride request cancelled. Captain route was released and the queue was updated.",
        )

    return MessageResponse(message="Ride request cancelled before captain acceptance.")
