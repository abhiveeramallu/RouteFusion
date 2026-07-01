from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Driver, Parcel, Ride, RouteDecision
from app.schemas import MessageResponse, ParcelCreate, ParcelRead
from app.services.locations import resolve_location_input

router = APIRouter(tags=["parcels"])

ACCEPTED_PARCEL_STATUSES = {"assigned", "assigned_solo"}
CLOSED_PARCEL_STATUSES = {"completed", "cancelled", "rejected"}


def latest_accepted_parcel_decision(db: Session, parcel_id: int) -> RouteDecision | None:
    return db.scalar(
        select(RouteDecision)
        .where(RouteDecision.parcel_id == parcel_id, RouteDecision.accepted.is_(True))
        .order_by(desc(RouteDecision.created_at))
    )


@router.post("/parcel", response_model=ParcelRead, status_code=status.HTTP_201_CREATED)
def create_parcel(
    payload: ParcelCreate,
    db: Session = Depends(get_db),
) -> Parcel:
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

    parcel = Parcel(
        pickup_name=pickup.name,
        drop_name=drop.name,
        pickup_lat=pickup.lat,
        pickup_lng=pickup.lng,
        drop_lat=drop.lat,
        drop_lng=drop.lng,
        parcel_weight=payload.parcel_weight,
        parcel_type=payload.parcel_type,
        priority=payload.priority,
    )
    db.add(parcel)
    db.commit()
    db.refresh(parcel)
    return parcel


@router.get("/parcel", response_model=list[ParcelRead])
def list_parcels(
    db: Session = Depends(get_db),
) -> list[Parcel]:
    return list(db.scalars(select(Parcel).order_by(desc(Parcel.created_at)).limit(10)))


@router.delete("/parcel/{parcel_id}", response_model=MessageResponse)
def cancel_parcel(
    parcel_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    parcel = db.get(Parcel, parcel_id)
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel request not found.")

    if parcel.status in CLOSED_PARCEL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This parcel can no longer be cancelled.",
        )

    decision = latest_accepted_parcel_decision(db, parcel.id)
    driver = db.get(Driver, decision.driver_id) if decision is not None else None
    linked_ride = db.get(Ride, decision.ride_id) if decision is not None else None
    was_accepted = parcel.status in ACCEPTED_PARCEL_STATUSES

    if parcel.status == "assigned" and linked_ride is not None and linked_ride.status == "confirmed":
        linked_ride.status = "open"

    parcel.status = "cancelled"

    if was_accepted and driver is not None:
        driver.status = "available"

    db.commit()

    if was_accepted:
        return MessageResponse(
            message="Parcel request cancelled. Captain route was released and the queue was updated.",
        )

    return MessageResponse(message="Parcel request cancelled before captain acceptance.")
