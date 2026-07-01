from __future__ import annotations

from sqlalchemy import delete, select
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Driver, Parcel, Ride, RouteDecision
from app.schemas import DemoClearResponse, DemoLoadResponse, DriverRead, ParcelRead, RideRead
from app.services.demo_seed import seed_demo_scenario

router = APIRouter(prefix="/demo", tags=["demo"])


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


@router.post("/clear", response_model=DemoClearResponse)
def clear_demo(
    db: Session = Depends(get_db),
) -> DemoClearResponse:
    cleared_decisions = db.query(RouteDecision).count()
    cleared_rides = db.query(Ride).count()
    cleared_parcels = db.query(Parcel).count()

    db.execute(delete(RouteDecision))
    db.execute(delete(Ride))
    db.execute(delete(Parcel))

    driver = db.scalar(select(Driver).limit(1))
    if driver:
        driver.status = "available"

    db.commit()

    return DemoClearResponse(
        cleared_rides=cleared_rides,
        cleared_parcels=cleared_parcels,
        cleared_decisions=cleared_decisions,
        message="All ride, parcel, and route decision data cleared.",
    )
