from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Driver, Parcel, RefreshToken, Ride, RouteDecision, TokenBlacklist
from app.services.locations import resolve_location


def reset_runtime_state(db: Session) -> dict[str, int]:
    cleared_decisions = db.query(RouteDecision).count()
    cleared_rides = db.query(Ride).count()
    cleared_parcels = db.query(Parcel).count()

    db.execute(delete(RouteDecision))
    db.execute(delete(Ride))
    db.execute(delete(Parcel))
    db.execute(delete(RefreshToken))
    db.execute(delete(TokenBlacklist))

    base_location = resolve_location("VIT Vellore")
    drivers = list(db.scalars(select(Driver)))
    for driver in drivers:
        driver.status = "available"
        driver.current_lat = base_location.lat + 0.003
        driver.current_lng = base_location.lng + 0.002

    db.commit()

    return {
        "cleared_rides": cleared_rides,
        "cleared_parcels": cleared_parcels,
        "cleared_decisions": cleared_decisions,
    }
