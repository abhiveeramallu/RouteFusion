from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import DemoClearResponse, DemoLoadResponse, DriverRead, ParcelRead, RideRead
from app.services.demo_seed import seed_demo_scenario
from app.services.runtime_state import reset_runtime_state

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
    cleared = reset_runtime_state(db)

    return DemoClearResponse(
        cleared_rides=cleared["cleared_rides"],
        cleared_parcels=cleared["cleared_parcels"],
        cleared_decisions=cleared["cleared_decisions"],
        message="All ride, parcel, and route decision data cleared.",
    )
