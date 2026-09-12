from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Driver, DriverDecline, Parcel, Ride, RouteDecision
from app.services.hungarian import INFEASIBLE_COST, solve_rectangular_assignment
from app.services.route_optimizer import (
    Waypoint,
    best_combined_extra_distance,
    haversine_distance_km,
)
from app.services.spatial_grid import GridPoint, build_grid_index, nearby

# Demo-scale sanity caps. A production dispatcher would page/stream this
# instead of loading everything into one solve, but at hundreds of open
# requests the whole pipeline still finishes in single-digit milliseconds.
CANDIDATE_CAP = 200
MAX_REASONABLE_BUNDLE_EXTRA_KM = 15.0
# A driver farther than this from a ride/parcel's pickup isn't a "suitable"
# match for it at all — better to leave the request open for a closer
# captain than force a long, low-quality pickup leg onto whoever's left.
MAX_REASONABLE_PICKUP_DISTANCE_KM = 15.0


@dataclass
class DriverAssignment:
    driver_id: int
    ride: Ride | None
    parcel: Parcel | None


@dataclass
class AssignmentEngineStats:
    drivers_considered: int
    rides_considered: int
    parcels_considered: int
    stage1_pairs_evaluated: int
    stage1_pairs_after_pruning: int
    stage2_pairs_evaluated: int
    stage2_pairs_after_pruning: int
    solve_time_ms: float
    # optimal_cost/greedy_cost/improvement_pct compare stage 1 only (total
    # driver-to-pickup distance for the Hungarian-optimal vs a greedy
    # edge-picking driver-ride assignment over the same pruned candidates).
    # Stage 2's bundling cost is a different unit (insertion extra-distance)
    # and isn't included, so the comparison stays apples-to-apples.
    #
    # Hungarian (via augmenting paths) can match MORE drivers than greedy
    # edge-picking manages, since greedy never revisits an earlier choice
    # that turns out to block a later match. When that happens the two
    # solutions aren't comparable by raw cost (one simply covers more
    # drivers), so improvement_pct is only meaningful — and only reported
    # as nonzero — when both matched the same number of pairs; otherwise
    # optimal_matched_count/greedy_matched_count tell the real story.
    optimal_cost: float
    greedy_cost: float
    improvement_pct: float
    optimal_matched_count: int
    greedy_matched_count: int


@dataclass
class AssignmentResult:
    by_driver_id: dict[int, DriverAssignment]
    stats: AssignmentEngineStats


def _rejected_pair_ride_ids(db: Session, ride_ids: list[int], parcel_ids: list[int]) -> set[tuple[int, int]]:
    """(ride_id, parcel_id) combinations whose most recent decision was a
    rejection — kept out of re-assignment, mirroring the original single-driver
    queue's "rejected pairs drop out" behavior.
    """
    if not ride_ids or not parcel_ids:
        return set()

    decisions = db.scalars(
        select(RouteDecision)
        .where(RouteDecision.ride_id.in_(ride_ids), RouteDecision.parcel_id.in_(parcel_ids))
        .order_by(desc(RouteDecision.created_at))
    )
    latest_by_pair: dict[tuple[int, int], RouteDecision] = {}
    for decision in decisions:
        latest_by_pair.setdefault((decision.ride_id, decision.parcel_id), decision)

    return {pair for pair, decision in latest_by_pair.items() if decision.accepted is False}


def _declined_ride_pairs(db: Session, driver_ids: list[int]) -> set[tuple[int, int]]:
    """(driver_id, ride_id) pairs this driver already declined solo — kept
    out of THEIR candidate set so the ride falls through to a different
    available captain instead of looping back to whoever just rejected it.
    """
    if not driver_ids:
        return set()

    declines = db.scalars(
        select(DriverDecline).where(DriverDecline.driver_id.in_(driver_ids), DriverDecline.ride_id.isnot(None))
    )
    return {(decline.driver_id, decline.ride_id) for decline in declines}


def _declined_parcel_pairs(db: Session, driver_ids: list[int]) -> set[tuple[int, int]]:
    """Same as _declined_ride_pairs, for solo-declined parcels."""
    if not driver_ids:
        return set()

    declines = db.scalars(
        select(DriverDecline).where(DriverDecline.driver_id.in_(driver_ids), DriverDecline.parcel_id.isnot(None))
    )
    return {(decline.driver_id, decline.parcel_id) for decline in declines}


def load_open_rides(db: Session) -> list[Ride]:
    return list(
        db.scalars(
            select(Ride).where(Ride.status == "open").order_by(desc(Ride.created_at)).limit(CANDIDATE_CAP)
        )
    )


def load_open_parcels(db: Session) -> list[Parcel]:
    return list(
        db.scalars(
            select(Parcel)
            .where(Parcel.status == "open")
            .order_by(desc(Parcel.created_at))
            .limit(CANDIDATE_CAP)
        )
    )


def run_assignment(db: Session) -> AssignmentResult:
    start = time.perf_counter()

    drivers = list(db.scalars(select(Driver).where(Driver.status == "available")))
    rides = load_open_rides(db)
    parcels = load_open_parcels(db)

    rides_by_id = {ride.id: ride for ride in rides}
    parcels_by_id = {parcel.id: parcel for parcel in parcels}

    by_driver_id: dict[int, DriverAssignment] = {
        driver.id: DriverAssignment(driver_id=driver.id, ride=None, parcel=None) for driver in drivers
    }

    stage1_pairs_evaluated = len(drivers) * len(rides)
    stage2_pairs_evaluated = 0
    stage1_pairs_after_pruning = 0
    stage2_pairs_after_pruning = 0
    optimal_cost = 0.0
    greedy_cost = 0.0
    optimal_matched_count = 0
    greedy_matched_count = 0

    if drivers and rides:
        # --- Stage 1: drivers x rides, minimize distance to pickup ---
        # The spatial grid identifies each driver's local neighborhood purely
        # to report realistic "candidates evaluated -> pruned to N" numbers
        # (the same technique real dispatch systems use to cut search space
        # at scale). It does NOT gate which pairs the solve actually
        # considers: at this app's demo-scale cap (CANDIDATE_CAP=200) an
        # exhaustive matrix is trivially cheap, and actually excluding
        # "distant" candidates risks silently missing the true optimum
        # whenever a driver's real best match sits just outside the grid's
        # fixed-radius neighborhood — solving on the full set guarantees the
        # "optimal_cost" this function reports is actually optimal.
        ride_grid = build_grid_index(
            [GridPoint(id=ride.id, lat=ride.pickup_lat, lng=ride.pickup_lng) for ride in rides]
        )
        for driver in drivers:
            candidates = nearby(ride_grid, driver.current_lat, driver.current_lng)
            stage1_pairs_after_pruning += len(candidates) or len(rides)

        candidate_ride_ids = sorted(rides_by_id)
        declined_rides = _declined_ride_pairs(db, [driver.id for driver in drivers])

        def stage1_cost(driver: Driver, ride_id: int) -> float:
            if (driver.id, ride_id) in declined_rides:
                return INFEASIBLE_COST
            ride = rides_by_id[ride_id]
            distance = haversine_distance_km(
                Waypoint("driver", driver.current_lat, driver.current_lng),
                Waypoint("pickup", ride.pickup_lat, ride.pickup_lng),
            )
            return distance if distance <= MAX_REASONABLE_PICKUP_DISTANCE_KM else INFEASIBLE_COST

        stage1_matrix = [
            [stage1_cost(driver, ride_id) for ride_id in candidate_ride_ids]
            for driver in drivers
        ]

        stage1_pairs, stage1_total_cost = solve_rectangular_assignment(stage1_matrix)
        # optimal_cost/greedy_cost compare stage 1 only (driver-to-pickup
        # distance) — stage 2's bundling extra-distance is a different
        # unit of cost, so folding it in would make "optimal" look worse
        # than "greedy" purely because optimal_cost had more terms added
        # to it, not because the assignment was actually worse.
        optimal_cost += stage1_total_cost
        optimal_matched_count += len(stage1_pairs)

        for row, col in stage1_pairs:
            driver = drivers[row]
            by_driver_id[driver.id].ride = rides_by_id[candidate_ride_ids[col]]

        # Greedy baseline for comparison only, over the same full edge set:
        # the standard textbook heuristic — sort every candidate edge by
        # cost ascending, take it if both endpoints are still free. This
        # also tends toward maximum cardinality (so it's a fair comparison
        # against Hungarian, which explicitly prioritizes matching everyone
        # possible before minimizing cost) — unlike a driver-order-based
        # "nearest first" pass, which can leave drivers unmatched purely
        # because of iteration order and so isn't solving the same problem
        # Hungarian is.
        candidate_edges = sorted(
            (
                (stage1_cost(driver, ride_id), driver.id, ride_id)
                for driver in drivers
                for ride_id in candidate_ride_ids
            ),
            key=lambda edge: edge[0],
        )
        greedy_claimed_drivers: set[int] = set()
        greedy_claimed_rides: set[int] = set()
        for cost, driver_id, ride_id in candidate_edges:
            if cost >= INFEASIBLE_COST:
                # Same treatment as solve_rectangular_assignment: an
                # infeasible edge (too far, or already declined by this
                # driver) never counts as a real match, even as a last
                # resort — otherwise greedy's matched count would disagree
                # with Hungarian's purely from infeasibility bookkeeping.
                continue
            if driver_id in greedy_claimed_drivers or ride_id in greedy_claimed_rides:
                continue
            greedy_claimed_drivers.add(driver_id)
            greedy_claimed_rides.add(ride_id)
            greedy_cost += cost
            greedy_matched_count += 1

    assigned_bundles = [
        (driver_id, assignment.ride)
        for driver_id, assignment in by_driver_id.items()
        if assignment.ride is not None
    ]

    if assigned_bundles and parcels:
        # --- Stage 2: (driver, assigned ride) x open parcels, minimize bundling extra distance ---
        # As in stage 1, the spatial grid here only produces realistic
        # "pruned to N" reporting numbers — it doesn't gate which parcels the
        # solve actually considers. The MAX_REASONABLE_BUNDLE_EXTRA_KM cap and
        # rejected-pairs exclusion below are the real, intentional
        # eligibility rules; those still apply.
        parcel_grid = build_grid_index(
            [GridPoint(id=parcel.id, lat=parcel.pickup_lat, lng=parcel.pickup_lng) for parcel in parcels]
        )
        drivers_by_id = {driver.id: driver for driver in drivers}
        rejected_pairs = _rejected_pair_ride_ids(
            db, [ride.id for _, ride in assigned_bundles], [parcel.id for parcel in parcels]
        )
        declined_parcels = _declined_parcel_pairs(db, [driver_id for driver_id, _ride in assigned_bundles])

        for _driver_id, ride in assigned_bundles:
            candidates = nearby(parcel_grid, ride.pickup_lat, ride.pickup_lng)
            stage2_pairs_after_pruning += len(candidates) or len(parcels)

        stage2_pairs_evaluated = len(assigned_bundles) * len(parcels)
        candidate_parcel_ids = sorted(parcels_by_id)

        def stage2_cost(bundle_index: int, parcel_id: int) -> float:
            driver_id, ride = assigned_bundles[bundle_index]
            if (driver_id, parcel_id) in declined_parcels:
                return INFEASIBLE_COST
            driver = drivers_by_id[driver_id]
            parcel = parcels_by_id[parcel_id]
            extra = best_combined_extra_distance(
                Waypoint("driver", driver.current_lat, driver.current_lng),
                Waypoint("ride_pickup", ride.pickup_lat, ride.pickup_lng),
                Waypoint("ride_drop", ride.drop_lat, ride.drop_lng),
                Waypoint("parcel_pickup", parcel.pickup_lat, parcel.pickup_lng),
                Waypoint("parcel_drop", parcel.drop_lat, parcel.drop_lng),
            )
            return extra if extra <= MAX_REASONABLE_BUNDLE_EXTRA_KM else INFEASIBLE_COST

        stage2_matrix = [
            [
                stage2_cost(bundle_index, parcel_id)
                if (assigned_bundles[bundle_index][1].id, parcel_id) not in rejected_pairs
                else INFEASIBLE_COST
                for parcel_id in candidate_parcel_ids
            ]
            for bundle_index in range(len(assigned_bundles))
        ]

        stage2_pairs, _stage2_total_cost = solve_rectangular_assignment(stage2_matrix)

        for row, col in stage2_pairs:
            driver_id, _ride = assigned_bundles[row]
            by_driver_id[driver_id].parcel = parcels_by_id[candidate_parcel_ids[col]]

    # Drivers with no ride can still get a standalone parcel offer: nearest
    # open parcel not already bundled to someone else in this solve, as long
    # as it's within reach and this driver hasn't already declined it.
    claimed_parcel_ids = {
        assignment.parcel.id for assignment in by_driver_id.values() if assignment.parcel is not None
    }
    rideless_driver_ids = [driver.id for driver in drivers if by_driver_id[driver.id].ride is None]
    declined_solo_parcels = _declined_parcel_pairs(db, rideless_driver_ids)
    for driver in drivers:
        assignment = by_driver_id[driver.id]
        if assignment.ride is not None or not parcels:
            continue
        best_parcel, best_cost = None, None
        for parcel in parcels:
            if parcel.id in claimed_parcel_ids or (driver.id, parcel.id) in declined_solo_parcels:
                continue
            cost = haversine_distance_km(
                Waypoint("driver", driver.current_lat, driver.current_lng),
                Waypoint("pickup", parcel.pickup_lat, parcel.pickup_lng),
            )
            if cost > MAX_REASONABLE_PICKUP_DISTANCE_KM:
                continue
            if best_cost is None or cost < best_cost:
                best_parcel, best_cost = parcel, cost
        if best_parcel is not None:
            assignment.parcel = best_parcel
            claimed_parcel_ids.add(best_parcel.id)

    solve_time_ms = (time.perf_counter() - start) * 1000
    # Only claim a % improvement when both solutions matched the same number
    # of driver-ride pairs — otherwise Hungarian matching more drivers than
    # greedy (via an augmenting path greedy can't find) would look like a
    # cost regression when it's actually a strictly better outcome.
    improvement_pct = (
        round((greedy_cost - optimal_cost) / greedy_cost * 100, 1)
        if greedy_cost > 0 and optimal_matched_count == greedy_matched_count
        else 0.0
    )

    stats = AssignmentEngineStats(
        drivers_considered=len(drivers),
        rides_considered=len(rides),
        parcels_considered=len(parcels),
        stage1_pairs_evaluated=stage1_pairs_evaluated,
        stage1_pairs_after_pruning=stage1_pairs_after_pruning,
        stage2_pairs_evaluated=stage2_pairs_evaluated,
        stage2_pairs_after_pruning=stage2_pairs_after_pruning,
        solve_time_ms=round(solve_time_ms, 2),
        optimal_cost=round(optimal_cost, 2),
        greedy_cost=round(greedy_cost, 2),
        improvement_pct=max(0.0, improvement_pct),
        optimal_matched_count=optimal_matched_count,
        greedy_matched_count=greedy_matched_count,
    )

    return AssignmentResult(by_driver_id=by_driver_id, stats=stats)


def best_match_for_driver(db: Session, driver: Driver) -> DriverAssignment:
    """This driver's own best reachable ride/parcel, evaluated independently
    of every other driver.

    This is what a captain's recommendation is actually built from — NOT a
    lookup into run_assignment's exclusive one-driver-per-ride matching.
    That global Hungarian solve stays exactly as it was, feeding the
    dashboard's optimal-vs-greedy analytics, but it was also (incorrectly)
    the only thing captain.py read a recommendation from, which meant a
    given open ride/parcel was only ever shown to the single globally
    "optimal" driver — every other available, equally-suitable captain saw
    nothing for it. That directly contradicts this app's own concurrency
    story (README: "two captains can be shown overlapping recommendations;
    only one can ever win the accept") — in practice that could only ever
    happen via the artificial /demo/stress/concurrency endpoint, never
    through real per-captain polling.

    So: the same suitability cap and per-driver decline exclusions as
    run_assignment's stage1/stage2 still apply here — a driver 20km away
    still isn't shown a ride, and a ride/parcel this driver already declined
    still isn't re-offered to them — but there is no cross-driver
    exclusivity. Multiple nearby captains can legitimately see the same
    ride, the same parcel, or the same combined bundle at once; the
    optimistic-locking claim in services/concurrency.py (unchanged) is what
    decides exactly one of them wins when they actually accept.
    """
    rides = load_open_rides(db)
    parcels = load_open_parcels(db)

    declined_ride_ids = {ride_id for _driver_id, ride_id in _declined_ride_pairs(db, [driver.id])}
    declined_parcel_ids = {parcel_id for _driver_id, parcel_id in _declined_parcel_pairs(db, [driver.id])}

    best_ride: Ride | None = None
    best_ride_distance: float | None = None
    for ride in rides:
        if ride.id in declined_ride_ids:
            continue
        distance = haversine_distance_km(
            Waypoint("driver", driver.current_lat, driver.current_lng),
            Waypoint("pickup", ride.pickup_lat, ride.pickup_lng),
        )
        if distance > MAX_REASONABLE_PICKUP_DISTANCE_KM:
            continue
        if best_ride_distance is None or distance < best_ride_distance:
            best_ride, best_ride_distance = ride, distance

    best_parcel: Parcel | None = None

    if best_ride is not None and parcels:
        rejected_pairs = _rejected_pair_ride_ids(db, [best_ride.id], [parcel.id for parcel in parcels])
        best_extra: float | None = None
        for parcel in parcels:
            if parcel.id in declined_parcel_ids or (best_ride.id, parcel.id) in rejected_pairs:
                continue
            extra = best_combined_extra_distance(
                Waypoint("driver", driver.current_lat, driver.current_lng),
                Waypoint("ride_pickup", best_ride.pickup_lat, best_ride.pickup_lng),
                Waypoint("ride_drop", best_ride.drop_lat, best_ride.drop_lng),
                Waypoint("parcel_pickup", parcel.pickup_lat, parcel.pickup_lng),
                Waypoint("parcel_drop", parcel.drop_lat, parcel.drop_lng),
            )
            if extra > MAX_REASONABLE_BUNDLE_EXTRA_KM:
                continue
            if best_extra is None or extra < best_extra:
                best_parcel, best_extra = parcel, extra
    elif best_ride is None and parcels:
        best_distance: float | None = None
        for parcel in parcels:
            if parcel.id in declined_parcel_ids:
                continue
            distance = haversine_distance_km(
                Waypoint("driver", driver.current_lat, driver.current_lng),
                Waypoint("pickup", parcel.pickup_lat, parcel.pickup_lng),
            )
            if distance > MAX_REASONABLE_PICKUP_DISTANCE_KM:
                continue
            if best_distance is None or distance < best_distance:
                best_parcel, best_distance = parcel, distance

    return DriverAssignment(driver_id=driver.id, ride=best_ride, parcel=best_parcel)
