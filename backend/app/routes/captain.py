from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth import ensure_captain_profile
from app.database import get_db
from app.dependencies import get_current_user_optional
from app.models import Driver, Parcel, Ride, RouteDecision, User
from app.schemas import (
    AcceptBothAnalysis,
    DriverRead,
    MessageResponse,
    ParcelRead,
    RecommendationAction,
    RecommendationActionResponse,
    RecommendationResponse,
    RideRead,
    RouteDecisionRead,
)
from app.services.assignment_engine import AssignmentResult, run_assignment
from app.services.concurrency import (
    PARCEL_STATUS_COMBINED,
    PARCEL_STATUS_SOLO,
    RIDE_STATUS_COMBINED,
    RIDE_STATUS_SOLO,
    attempt_accept,
)
from app.services.demo_seed import ensure_demo_driver
from app.services.pricing import estimate_customer_pricing, estimate_parcel_base_price, estimate_ride_base_price
from app.services.route_optimizer import Waypoint, optimize_route

router = APIRouter(prefix="/captain", tags=["captain"])

SOLO_ROUTE_EFFICIENCY = 100.0
RIDE_STATUS_COMPLETED = "completed"
PARCEL_STATUS_COMPLETED = "completed"


def decision_mode_from_statuses(ride: Ride, parcel: Parcel) -> str:
    if ride.status == RIDE_STATUS_COMBINED and parcel.status == PARCEL_STATUS_COMBINED:
        return "combined"
    if ride.status == RIDE_STATUS_SOLO:
        return "ride_only"
    if parcel.status == PARCEL_STATUS_SOLO:
        return "parcel_only"
    return "pending"


def decision_mode_from_recommendation(value: str | None) -> str:
    mapping = {
        "accept_both": "combined",
        "accept_ride": "ride_only",
        "accept_parcel": "parcel_only",
    }
    return mapping.get((value or "").lower(), "pending")


def confirmation_status_for_mode(mode: str) -> str:
    return {
        "combined": "Combined ride and parcel confirmed",
        "ride_only": "Ride accepted individually",
        "parcel_only": "Parcel accepted individually",
    }.get(mode, "Awaiting Captain Decision")


def confirmed_recommendation_label(mode: str) -> str:
    return {
        "combined": "ACCEPT BOTH",
        "ride_only": "RIDE ONLY CONFIRMED",
        "parcel_only": "PARCEL ONLY CONFIRMED",
    }.get(mode, "PENDING")


def recommendation_status(mode: str, route_confirmed: bool) -> str:
    if route_confirmed:
        return confirmation_status_for_mode(mode)

    return {
        "ride_only": "Ride request is ready for captain acceptance",
        "parcel_only": "Parcel request is ready for captain acceptance",
    }.get(mode, "AI recommendation is ready for captain review")


def build_payment_collection_message(recommendation: RecommendationResponse) -> str:
    if recommendation.decision_mode == "combined":
        return (
            "Combined route completed. "
            f"Collect Rs {int(round(recommendation.ride_customer_price))} from the passenger "
            f"and Rs {int(round(recommendation.parcel_customer_price))} from the parcel sender."
        )

    if recommendation.decision_mode == "ride_only":
        return (
            "Ride completed. "
            f"Collect Rs {int(round(recommendation.ride_customer_price))} from the passenger."
        )

    return (
        "Parcel completed. "
        f"Collect Rs {int(round(recommendation.parcel_customer_price))} from the parcel sender."
    )


def final_route_point_for_recommendation(recommendation: RecommendationResponse) -> dict[str, float | str] | None:
    if recommendation.decision_mode == "ride_only" and recommendation.passenger_route:
        return recommendation.passenger_route[-1].model_dump()

    if recommendation.decision_mode == "parcel_only" and recommendation.parcel_route:
        return recommendation.parcel_route[-1].model_dump()

    if recommendation.optimized_route:
        return recommendation.optimized_route[-1].model_dump()

    return None


def ride_route_points(ride: Ride | None) -> list[dict[str, float | str]]:
    if ride is None:
        return []

    return [
        {"name": ride.pickup_name, "lat": ride.pickup_lat, "lng": ride.pickup_lng},
        {"name": ride.drop_name, "lat": ride.drop_lat, "lng": ride.drop_lng},
    ]


def parcel_route_points(parcel: Parcel | None) -> list[dict[str, float | str]]:
    if parcel is None:
        return []

    return [
        {"name": parcel.pickup_name, "lat": parcel.pickup_lat, "lng": parcel.pickup_lng},
        {"name": parcel.drop_name, "lat": parcel.drop_lat, "lng": parcel.drop_lng},
    ]


def optimize_combined_route(driver: Driver, ride: Ride, parcel: Parcel) -> dict[str, object]:
    return optimize_route(
        driver_location=Waypoint(driver.display_name, driver.current_lat, driver.current_lng),
        ride_pickup=Waypoint(ride.pickup_name, ride.pickup_lat, ride.pickup_lng),
        ride_drop=Waypoint(ride.drop_name, ride.drop_lat, ride.drop_lng),
        parcel_pickup=Waypoint(parcel.pickup_name, parcel.pickup_lat, parcel.pickup_lng),
        parcel_drop=Waypoint(parcel.drop_name, parcel.drop_lat, parcel.drop_lng),
    )


def accept_both_candidate(optimization: dict[str, object] | None) -> dict[str, object] | None:
    if optimization is None:
        return None

    candidate_options = optimization.get("candidate_options")
    if not isinstance(candidate_options, dict):
        return None

    option = candidate_options.get("accept_both")
    return option if isinstance(option, dict) else None


def option_sequence_points(option: dict[str, object] | None) -> list[dict[str, float | str]]:
    if option is None:
        return []

    sequence = option.get("sequence")
    if not isinstance(sequence, list):
        return []

    return [
        {
            "name": str(point.get("name", "")),
            "lat": float(point.get("lat", 0.0)),
            "lng": float(point.get("lng", 0.0)),
        }
        for point in sequence
        if isinstance(point, dict)
    ]


def solo_pricing(ride: Ride | None = None, parcel: Parcel | None = None) -> dict[str, float]:
    if ride is not None:
        ride_base_price = estimate_ride_base_price(ride)
        return {
            "ride_base_price": ride_base_price,
            "parcel_base_price": 0.0,
            "ride_customer_price": ride_base_price,
            "parcel_customer_price": 0.0,
            "combined_customer_total": ride_base_price,
            "estimated_customer_savings": 0.0,
        }

    if parcel is not None:
        parcel_base_price = estimate_parcel_base_price(parcel)
        return {
            "ride_base_price": 0.0,
            "parcel_base_price": parcel_base_price,
            "ride_customer_price": 0.0,
            "parcel_customer_price": parcel_base_price,
            "combined_customer_total": parcel_base_price,
            "estimated_customer_savings": 0.0,
        }

    return {
        "ride_base_price": 0.0,
        "parcel_base_price": 0.0,
        "ride_customer_price": 0.0,
        "parcel_customer_price": 0.0,
        "combined_customer_total": 0.0,
        "estimated_customer_savings": 0.0,
    }


def serialize_decision(
    decision: RouteDecision | None,
    ride: Ride | None = None,
    parcel: Parcel | None = None,
) -> RouteDecisionRead | None:
    if not decision:
        return None

    decision_mode = (
        decision_mode_from_statuses(ride, parcel)
        if ride is not None and parcel is not None and decision.accepted
        else decision_mode_from_recommendation(decision.recommendation)
    )

    return RouteDecisionRead(
        id=decision.id,
        efficiency_score=decision.efficiency_score,
        extra_distance=decision.extra_distance,
        extra_time=decision.extra_time,
        overlap_distance=decision.overlap_distance,
        recommendation=decision.recommendation,
        decision_mode=decision_mode,
        accepted=decision.accepted,
        created_at=decision.created_at,
    )


def get_latest_pair_decision(db: Session, ride_id: int, parcel_id: int) -> RouteDecision | None:
    return db.scalar(
        select(RouteDecision)
        .where(RouteDecision.ride_id == ride_id, RouteDecision.parcel_id == parcel_id)
        .order_by(desc(RouteDecision.created_at))
    )


def get_latest_ride_decision(db: Session, ride_id: int) -> RouteDecision | None:
    return db.scalar(
        select(RouteDecision)
        .where(RouteDecision.ride_id == ride_id)
        .order_by(desc(RouteDecision.created_at))
    )


def get_latest_parcel_decision(db: Session, parcel_id: int) -> RouteDecision | None:
    return db.scalar(
        select(RouteDecision)
        .where(RouteDecision.parcel_id == parcel_id)
        .order_by(desc(RouteDecision.created_at))
    )


def get_active_assignment(
    db: Session, driver: Driver
) -> tuple[Ride | None, Parcel | None, RouteDecision | None, str] | None:
    """A driver's currently confirmed ride/parcel, if any. Scoped by
    `assigned_driver_id` — without this, any captain would see (and could
    complete) whichever driver's trip happened to be the most recently
    confirmed system-wide, which was invisible with only one driver in the
    demo but breaks immediately with real multi-captain accounts.
    """
    ride = db.scalar(
        select(Ride)
        .where(Ride.assigned_driver_id == driver.id, Ride.status.in_([RIDE_STATUS_COMBINED, RIDE_STATUS_SOLO]))
        .order_by(desc(Ride.created_at))
    )
    parcel = db.scalar(
        select(Parcel)
        .where(
            Parcel.assigned_driver_id == driver.id,
            Parcel.status.in_([PARCEL_STATUS_COMBINED, PARCEL_STATUS_SOLO]),
        )
        .order_by(desc(Parcel.created_at))
    )

    if ride is not None and ride.status == RIDE_STATUS_SOLO:
        return ride, None, get_latest_ride_decision(db, ride.id), "ride_only"

    if parcel is not None and parcel.status == PARCEL_STATUS_SOLO:
        return None, parcel, get_latest_parcel_decision(db, parcel.id), "parcel_only"

    if ride is None or parcel is None:
        return None

    decision_mode = decision_mode_from_statuses(ride, parcel)
    if decision_mode != "combined":
        return None

    return ride, parcel, get_latest_pair_decision(db, ride.id, parcel.id), decision_mode


def resolve_driver_for_user(db: Session, user: User | None) -> Driver:
    """Anonymous/public traffic (no token, or an operator) falls back to the
    single shared demo driver — the app's original public-demo behavior. A
    logged-in captain gets their own driver profile instead, which is what
    makes multiple real captain accounts see genuinely different queues.
    """
    if user is not None and user.driver is not None:
        return user.driver
    if user is not None and user.role == "captain":
        return ensure_captain_profile(db, user)
    return ensure_demo_driver(db)


def build_recommendation(
    db: Session,
    current_user: User | None,
    engine_result: AssignmentResult | None = None,
) -> RecommendationResponse:
    driver = resolve_driver_for_user(db, current_user)
    active_assignment = get_active_assignment(db, driver)
    route_confirmed = active_assignment is not None
    optimization: dict[str, object] | None = None

    if active_assignment is not None:
        ride, parcel, latest_decision, decision_mode = active_assignment
        optimization = (
            optimize_combined_route(driver, ride, parcel)
            if decision_mode == "combined" and ride is not None and parcel is not None
            else None
        )
        combined_option = accept_both_candidate(optimization) if decision_mode == "combined" else None
        if decision_mode == "combined" and combined_option is not None:
            efficiency_score = float(combined_option["efficiency_score"])
            extra_distance = float(combined_option["extra_distance"])
            extra_time = float(combined_option["extra_time"])
            overlap_distance = float(combined_option["overlap_distance"])
        elif latest_decision is not None:
            efficiency_score = latest_decision.efficiency_score
            extra_distance = latest_decision.extra_distance if decision_mode == "combined" else 0.0
            extra_time = latest_decision.extra_time if decision_mode == "combined" else 0.0
            overlap_distance = latest_decision.overlap_distance if decision_mode == "combined" else 0.0
        elif decision_mode == "combined" and optimization is not None:
            efficiency_score = float(optimization["efficiency_score"])
            extra_distance = float(optimization["extra_distance"])
            extra_time = float(optimization["extra_time"])
            overlap_distance = float(optimization["overlap_distance"])
        else:
            efficiency_score = SOLO_ROUTE_EFFICIENCY
            extra_distance = 0.0
            extra_time = 0.0
            overlap_distance = 0.0
    else:
        # A caller that already ran the fleet-wide solve this request (e.g.
        # GET /snapshot, which also needs it for /dashboard) can pass the
        # result through instead of paying for the full two-stage Hungarian
        # solve a second time for the same, unchanged DB state.
        if engine_result is None:
            engine_result = run_assignment(db)
        assignment = engine_result.by_driver_id.get(driver.id)
        ride = assignment.ride if assignment is not None else None
        parcel = assignment.parcel if assignment is not None else None
        latest_decision = None

        if ride is not None and parcel is not None:
            optimization = optimize_combined_route(driver, ride, parcel)
            latest_decision = get_latest_pair_decision(db, ride.id, parcel.id)
            decision_mode = "pending"
            efficiency_score = float(optimization["efficiency_score"])
            extra_distance = float(optimization["extra_distance"])
            extra_time = float(optimization["extra_time"])
            overlap_distance = float(optimization["overlap_distance"])
        elif ride is not None:
            latest_decision = get_latest_ride_decision(db, ride.id)
            decision_mode = "ride_only"
            efficiency_score = SOLO_ROUTE_EFFICIENCY
            extra_distance = 0.0
            extra_time = 0.0
            overlap_distance = 0.0
        elif parcel is not None:
            latest_decision = get_latest_parcel_decision(db, parcel.id)
            decision_mode = "parcel_only"
            efficiency_score = SOLO_ROUTE_EFFICIENCY
            extra_distance = 0.0
            extra_time = 0.0
            overlap_distance = 0.0
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active recommendation is available right now. Create or reload requests to continue.",
            )

    if decision_mode == "ride_only":
        pricing = solo_pricing(ride=ride)
        ride_customer_price = pricing["ride_customer_price"]
        parcel_customer_price = 0.0
        combined_customer_total = pricing["combined_customer_total"]
        estimated_customer_savings = pricing["estimated_customer_savings"]
        passenger_route = ride_route_points(ride)
        parcel_route = []
        optimized_route = passenger_route
    elif decision_mode == "parcel_only":
        pricing = solo_pricing(parcel=parcel)
        ride_customer_price = 0.0
        parcel_customer_price = pricing["parcel_customer_price"]
        combined_customer_total = pricing["combined_customer_total"]
        estimated_customer_savings = pricing["estimated_customer_savings"]
        passenger_route = []
        parcel_route = parcel_route_points(parcel)
        optimized_route = parcel_route
    else:
        if ride is None or parcel is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="RouteFusion could not build the combined recommendation state.",
            )

        pricing = estimate_customer_pricing(
            ride=ride,
            parcel=parcel,
            overlap_distance=overlap_distance,
            extra_time=extra_time,
        )
        ride_customer_price = pricing["ride_customer_price"]
        parcel_customer_price = pricing["parcel_customer_price"]
        combined_customer_total = pricing["combined_customer_total"]
        estimated_customer_savings = pricing["estimated_customer_savings"]
        passenger_route = ride_route_points(ride)
        parcel_route = parcel_route_points(parcel)
        optimized_route = option_sequence_points(accept_both_candidate(optimization)) or (
            optimization["optimized_route"] if optimization is not None else passenger_route
        )

    if route_confirmed:
        recommendation_label = confirmed_recommendation_label(decision_mode)
    elif decision_mode == "ride_only":
        recommendation_label = "ACCEPT RIDE"
    elif decision_mode == "parcel_only":
        recommendation_label = "ACCEPT PARCEL"
    else:
        recommendation_label = str(optimization["recommendation"]) if optimization is not None else "PENDING"

    accept_both_analysis = (
        AcceptBothAnalysis(**optimization["accept_both_analysis"]) if optimization is not None else None
    )

    return RecommendationResponse(
        driver=DriverRead.model_validate(driver),
        ride=RideRead.model_validate(ride) if ride is not None else None,
        parcel=ParcelRead.model_validate(parcel) if parcel is not None else None,
        efficiency_score=efficiency_score,
        extra_distance=extra_distance,
        extra_time=extra_time,
        overlap_distance=overlap_distance,
        recommendation=recommendation_label,
        decision_mode=decision_mode,
        route_confirmed=route_confirmed,
        confirmation_status=recommendation_status(decision_mode, route_confirmed),
        ride_customer_price=ride_customer_price,
        parcel_customer_price=parcel_customer_price,
        combined_customer_total=combined_customer_total,
        estimated_customer_savings=estimated_customer_savings,
        passenger_route=passenger_route,
        parcel_route=parcel_route,
        optimized_route=optimized_route,
        recent_decision=serialize_decision(latest_decision, ride, parcel),
        accept_both_analysis=accept_both_analysis,
    )


@router.get("/recommendations", response_model=RecommendationResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> RecommendationResponse:
    return build_recommendation(db, current_user)


@router.post("/recommendations/respond", response_model=RecommendationActionResponse)
def respond_to_recommendation(
    payload: RecommendationAction,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> RecommendationActionResponse:
    recommendation = build_recommendation(db, current_user)

    if payload.decision == "accept_both" and (recommendation.ride is None or recommendation.parcel is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A combined acceptance needs both a ride and a parcel request.",
        )

    if payload.decision == "accept_ride" and recommendation.ride is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ride is available for captain acceptance right now.",
        )

    if payload.decision == "accept_parcel" and recommendation.parcel is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No parcel is available for captain acceptance right now.",
        )

    decision_efficiency = recommendation.efficiency_score
    decision_extra_distance = recommendation.extra_distance
    decision_extra_time = recommendation.extra_time
    decision_overlap_distance = recommendation.overlap_distance
    ride = db.get(Ride, recommendation.ride.id) if recommendation.ride is not None else None
    parcel = db.get(Parcel, recommendation.parcel.id) if recommendation.parcel is not None else None
    driver = db.get(Driver, recommendation.driver.id)

    if recommendation.ride is not None and recommendation.parcel is not None:
        if payload.decision == "accept_both" and ride is not None and parcel is not None and driver is not None:
            combined_optimization = optimize_combined_route(driver, ride, parcel)
            combined_option = accept_both_candidate(combined_optimization)
            if combined_option is not None:
                decision_efficiency = float(combined_option["efficiency_score"])
                decision_extra_distance = float(combined_option["extra_distance"])
                decision_extra_time = float(combined_option["extra_time"])
                decision_overlap_distance = float(combined_option["overlap_distance"])
        elif payload.decision in ("accept_ride", "accept_parcel"):
            # The default above (recommendation.efficiency_score, etc.) is
            # the SCORED BUNDLE's numbers. Declining the bundle in favor of
            # a solo ride/parcel is a different, unscored outcome — record
            # the actual solo metrics instead of misattributing the bundle's
            # score to a trip that was never combined.
            decision_efficiency = SOLO_ROUTE_EFFICIENCY
            decision_extra_distance = 0.0
            decision_extra_time = 0.0
            decision_overlap_distance = 0.0

    outcome = attempt_accept(
        db,
        decision=payload.decision,
        driver_id=recommendation.driver.id,
        ride_id=ride.id if ride is not None else None,
        parcel_id=parcel.id if parcel is not None else None,
    )
    if not outcome.success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=outcome.conflict_reason)

    decision: RouteDecision | None = None
    if recommendation.ride is not None and recommendation.parcel is not None:
        decision = RouteDecision(
            driver_id=recommendation.driver.id,
            ride_id=recommendation.ride.id,
            parcel_id=recommendation.parcel.id,
            efficiency_score=decision_efficiency,
            extra_distance=decision_extra_distance,
            extra_time=decision_extra_time,
            overlap_distance=decision_overlap_distance,
            recommendation=payload.decision,
            accepted=payload.decision != "reject",
        )
        db.add(decision)

    db.commit()
    if decision is not None:
        db.refresh(decision)

    if payload.decision == "accept_both":
        message = "Combined route accepted. Ride and parcel are locked together with customer pricing."
    elif payload.decision == "accept_ride" and parcel is None:
        message = "Ride accepted. The live map is now following the passenger route."
    elif payload.decision == "accept_ride":
        message = "Ride accepted individually. The passenger route is locked and the parcel stays in the queue."
    elif payload.decision == "accept_parcel" and ride is None:
        message = "Parcel accepted. The live map is now following the parcel route."
    elif payload.decision == "accept_parcel":
        message = "Parcel accepted individually. The parcel route is locked and the ride stays in the queue."
    elif ride is not None and parcel is None:
        message = "Ride rejected. RouteFusion moved to the next ride in the queue."
    elif parcel is not None and ride is None:
        message = "Parcel rejected. RouteFusion moved to the next parcel in the queue."
    else:
        message = "Recommendation rejected. Requests moved back into the open pool."

    return RecommendationActionResponse(
        message=message,
        decision=serialize_decision(decision, ride, parcel),
    )


@router.post("/recommendations/complete", response_model=MessageResponse)
def complete_active_recommendation(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> MessageResponse:
    driver = resolve_driver_for_user(db, current_user)
    active_assignment = get_active_assignment(db, driver)
    if active_assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active captain route is available to complete right now.",
        )

    recommendation = build_recommendation(db, current_user)
    ride = db.get(Ride, recommendation.ride.id) if recommendation.ride is not None else None
    parcel = db.get(Parcel, recommendation.parcel.id) if recommendation.parcel is not None else None
    driver = db.get(Driver, recommendation.driver.id)

    if ride is not None:
        ride.status = RIDE_STATUS_COMPLETED
    if parcel is not None:
        parcel.status = PARCEL_STATUS_COMPLETED
    if driver is not None:
        final_point = final_route_point_for_recommendation(recommendation)
        if final_point is not None:
            driver.current_lat = float(final_point["lat"])
            driver.current_lng = float(final_point["lng"])
        driver.status = "available"

    db.commit()

    return MessageResponse(
        message=f"{build_payment_collection_message(recommendation)} Captain is now available for the next queue item.",
    )
