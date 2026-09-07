from __future__ import annotations

from itertools import chain

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_optional
from app.models import ConcurrencyEvent, Driver, Parcel, Ride, RouteDecision, User
from app.routes.captain import build_recommendation
from app.schemas import (
    ActivityItem,
    AppSnapshotResponse,
    AssignmentEngineStats,
    ConcurrencyStats,
    DashboardMetrics,
    DashboardResponse,
)
from app.services.assignment_engine import AssignmentResult, run_assignment
from app.services.pricing import (
    estimate_customer_pricing,
    estimate_parcel_base_price,
    estimate_ride_base_price,
)
from app.services.route_optimizer import Waypoint, route_distance_km

router = APIRouter(tags=["dashboard"])

COMBINED_RIDE_HANDLED_STATUSES = {"confirmed", "completed"}
COMBINED_PARCEL_HANDLED_STATUSES = {"assigned", "completed"}
COMBINED_RIDE_PAID_STATUSES = {"completed"}
COMBINED_PARCEL_PAID_STATUSES = {"completed"}
SOLO_RIDE_HANDLED_STATUSES = {"confirmed_solo", "completed"}
SOLO_PARCEL_HANDLED_STATUSES = {"assigned_solo", "completed"}
SOLO_RIDE_PAID_STATUSES = {"completed"}
SOLO_PARCEL_PAID_STATUSES = {"completed"}


def humanize_value(value: str) -> str:
    return value.replace("_", " ").title()


def build_captain_summary(
    db: Session,
    accepted_decisions: list[RouteDecision],
) -> tuple[float, int, int, int]:
    latest_decisions_by_pair: dict[tuple[int, int], RouteDecision] = {}
    for decision in accepted_decisions:
        latest_decisions_by_pair.setdefault((decision.ride_id, decision.parcel_id), decision)

    ride_ids = {decision.ride_id for decision in latest_decisions_by_pair.values()}
    parcel_ids = {decision.parcel_id for decision in latest_decisions_by_pair.values()}
    rides_by_id = {
        ride.id: ride
        for ride in db.scalars(select(Ride).where(Ride.id.in_(ride_ids)))
    } if ride_ids else {}
    parcels_by_id = {
        parcel.id: parcel
        for parcel in db.scalars(select(Parcel).where(Parcel.id.in_(parcel_ids)))
    } if parcel_ids else {}

    combined_handled_ride_ids: set[int] = set()
    combined_handled_parcel_ids: set[int] = set()
    combined_paid_ride_ids: set[int] = set()
    combined_paid_parcel_ids: set[int] = set()
    captain_total_earnings = 0.0
    captain_combined_trips = 0

    for decision in latest_decisions_by_pair.values():
        ride = rides_by_id.get(decision.ride_id)
        parcel = parcels_by_id.get(decision.parcel_id)
        if not ride or not parcel:
            continue

        if (
            decision.recommendation == "accept_both"
            and ride.status in COMBINED_RIDE_HANDLED_STATUSES
            and parcel.status in COMBINED_PARCEL_HANDLED_STATUSES
        ):
            captain_combined_trips += 1
            combined_handled_ride_ids.add(ride.id)
            combined_handled_parcel_ids.add(parcel.id)

        if (
            decision.recommendation == "accept_both"
            and ride.status in COMBINED_RIDE_PAID_STATUSES
            and parcel.status in COMBINED_PARCEL_PAID_STATUSES
        ):
            pricing = estimate_customer_pricing(
                ride=ride,
                parcel=parcel,
                overlap_distance=decision.overlap_distance,
                extra_time=decision.extra_time,
            )
            captain_total_earnings += pricing["combined_customer_total"]
            combined_paid_ride_ids.add(ride.id)
            combined_paid_parcel_ids.add(parcel.id)

    solo_rides = list(
        db.scalars(
            select(Ride).where(Ride.status.in_(tuple(SOLO_RIDE_HANDLED_STATUSES))).order_by(desc(Ride.created_at))
        )
    )
    solo_parcels = list(
        db.scalars(
            select(Parcel).where(Parcel.status.in_(tuple(SOLO_PARCEL_HANDLED_STATUSES))).order_by(desc(Parcel.created_at))
        )
    )

    captain_rides_handled = len(combined_handled_ride_ids)
    captain_parcels_handled = len(combined_handled_parcel_ids)

    for ride in solo_rides:
        if ride.id in combined_handled_ride_ids:
            continue
        captain_rides_handled += 1
        if ride.status in SOLO_RIDE_PAID_STATUSES and ride.id not in combined_paid_ride_ids:
            captain_total_earnings += estimate_ride_base_price(ride)

    for parcel in solo_parcels:
        if parcel.id in combined_handled_parcel_ids:
            continue
        captain_parcels_handled += 1
        if parcel.status in SOLO_PARCEL_PAID_STATUSES and parcel.id not in combined_paid_parcel_ids:
            captain_total_earnings += estimate_parcel_base_price(parcel)

    return (
        round(captain_total_earnings, 2),
        captain_rides_handled,
        captain_parcels_handled,
        captain_combined_trips,
    )


def build_dashboard_response(
    db: Session,
    engine_result: AssignmentResult | None = None,
) -> DashboardResponse:
    total_rides = db.scalar(select(func.count()).select_from(Ride)) or 0
    total_parcels = db.scalar(select(func.count()).select_from(Parcel)) or 0
    accepted_decisions = list(
        db.scalars(
            select(RouteDecision)
            .where(RouteDecision.accepted.is_(True))
            .order_by(desc(RouteDecision.created_at))
        )
    )
    combined_decisions = [
        decision for decision in accepted_decisions if decision.recommendation == "accept_both"
    ]
    total_combined_trips = len(combined_decisions)
    active_captains = db.scalar(
        select(func.count()).select_from(Driver).where(Driver.status == "available")
    ) or 0
    average_efficiency = round(
        sum(decision.efficiency_score for decision in combined_decisions) / total_combined_trips, 1
    ) if total_combined_trips else 0.0
    (
        captain_total_earnings,
        captain_rides_handled,
        captain_parcels_handled,
        captain_combined_trips,
    ) = build_captain_summary(db, accepted_decisions)

    combined_parcel_ids = {decision.parcel_id for decision in combined_decisions}
    combined_parcels_by_id = {
        parcel.id: parcel
        for parcel in db.scalars(select(Parcel).where(Parcel.id.in_(combined_parcel_ids)))
    } if combined_parcel_ids else {}

    estimated_fuel_saved = 0.0
    for decision in combined_decisions:
        parcel = combined_parcels_by_id.get(decision.parcel_id)
        if not parcel:
            continue
        parcel_distance = route_distance_km(
            [
                Waypoint(parcel.pickup_name, parcel.pickup_lat, parcel.pickup_lng),
                Waypoint(parcel.drop_name, parcel.drop_lat, parcel.drop_lng),
            ]
        )
        estimated_fuel_saved += max(0.0, parcel_distance - decision.extra_distance) * 0.11

    recent_rides = list(db.scalars(select(Ride).order_by(desc(Ride.created_at)).limit(5)))
    recent_parcels = list(db.scalars(select(Parcel).order_by(desc(Parcel.created_at)).limit(5)))
    recent_decisions = list(db.scalars(select(RouteDecision).order_by(desc(RouteDecision.created_at)).limit(5)))

    activities = [
        ActivityItem(
            timestamp=ride.created_at,
            activity_type="Ride Request",
            route_label=f"{ride.pickup_name} -> {ride.drop_name}",
            status=humanize_value(ride.status),
            recommendation="Pending",
            efficiency_score=None,
        )
        for ride in recent_rides
    ] + [
        ActivityItem(
            timestamp=parcel.created_at,
            activity_type="Parcel Request",
            route_label=f"{parcel.pickup_name} -> {parcel.drop_name}",
            status=humanize_value(parcel.status),
            recommendation=parcel.priority,
            efficiency_score=None,
        )
        for parcel in recent_parcels
    ] + [
        ActivityItem(
            timestamp=decision.created_at,
            activity_type="Route Decision",
            route_label=f"Ride #{decision.ride_id} + Parcel #{decision.parcel_id}",
            status="Accepted" if decision.accepted else "Rejected",
            recommendation=humanize_value(decision.recommendation),
            efficiency_score=decision.efficiency_score,
        )
        for decision in recent_decisions
    ]
    activities = sorted(chain(activities), key=lambda item: item.timestamp, reverse=True)[:10]

    if engine_result is None:
        engine_result = run_assignment(db)
    stats = engine_result.stats

    concurrency_events = list(
        db.scalars(select(ConcurrencyEvent).order_by(desc(ConcurrencyEvent.created_at)))
    )
    conflicts_prevented = sum(event.conflicts for event in concurrency_events)
    last_event = concurrency_events[0] if concurrency_events else None
    last_event_summary = (
        f"Ride #{last_event.ride_id} + Parcel #{last_event.parcel_id}: "
        f"{last_event.succeeded} succeeded, {last_event.conflicts} conflicted"
        if last_event is not None
        else None
    )

    return DashboardResponse(
        metrics=DashboardMetrics(
            total_rides=total_rides,
            total_parcels=total_parcels,
            total_combined_trips=total_combined_trips,
            active_captains=active_captains,
            average_efficiency_score=average_efficiency,
            estimated_fuel_saved=round(estimated_fuel_saved, 2),
            captain_total_earnings=captain_total_earnings,
            captain_rides_handled=captain_rides_handled,
            captain_parcels_handled=captain_parcels_handled,
            captain_combined_trips=captain_combined_trips,
        ),
        recent_activity=activities,
        assignment_engine=AssignmentEngineStats(
            drivers_considered=stats.drivers_considered,
            rides_considered=stats.rides_considered,
            parcels_considered=stats.parcels_considered,
            stage1_pairs_evaluated=stats.stage1_pairs_evaluated,
            stage1_pairs_after_pruning=stats.stage1_pairs_after_pruning,
            stage2_pairs_evaluated=stats.stage2_pairs_evaluated,
            stage2_pairs_after_pruning=stats.stage2_pairs_after_pruning,
            solve_time_ms=stats.solve_time_ms,
            optimal_cost=stats.optimal_cost,
            greedy_cost=stats.greedy_cost,
            improvement_pct=stats.improvement_pct,
            optimal_matched_count=stats.optimal_matched_count,
            greedy_matched_count=stats.greedy_matched_count,
        ),
        concurrency=ConcurrencyStats(
            conflicts_prevented=conflicts_prevented,
            stress_tests_run=len(concurrency_events),
            last_event_summary=last_event_summary,
        ),
    )


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    return build_dashboard_response(db)


@router.get("/snapshot", response_model=AppSnapshotResponse)
def get_snapshot(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> AppSnapshotResponse:
    # Computed once and threaded through both calls below — build_recommendation
    # and build_dashboard_response each independently need the fleet-wide
    # assignment solve, and re-running the full two-stage Hungarian pipeline
    # twice for the same, unchanged DB state on every /snapshot call (the
    # single call the frontend makes on nearly every action) would double
    # its cost for no benefit.
    engine_result = run_assignment(db)

    recommendation = None
    try:
        recommendation = build_recommendation(db, current_user, engine_result)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise

    rides = list(db.scalars(select(Ride).order_by(desc(Ride.created_at))))
    parcels = list(db.scalars(select(Parcel).order_by(desc(Parcel.created_at))))

    return AppSnapshotResponse(
        dashboard=build_dashboard_response(db, engine_result),
        recommendation=recommendation,
        rides=rides,
        parcels=parcels,
    )
