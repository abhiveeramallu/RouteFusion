from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import permutations
from math import atan2, cos, radians, sin, sqrt

AVERAGE_SPEED_KMH = 28.0

# The single source of truth for the ACCEPT BOTH decision thresholds — used
# both to decide the recommendation below and to report the pass/fail
# breakdown in accept_both_analysis, so the UI never hardcodes or
# re-derives these numbers independently of what the backend actually used.
ACCEPT_BOTH_MIN_EFFICIENCY_SCORE = 75.0
ACCEPT_BOTH_MAX_EXTRA_TIME_MIN = 12.0
ACCEPT_BOTH_MAX_PASSENGER_DELAY_KM = 3.0


@dataclass(frozen=True)
class Waypoint:
    name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class OptionScore:
    label: str
    sequence: list[Waypoint]
    total_distance: float
    passenger_distance: float
    extra_distance: float
    passenger_delay: float
    overlap_distance: float
    extra_time: float
    efficiency_score: float


def haversine_distance_km(start: Waypoint, end: Waypoint) -> float:
    earth_radius_km = 6371.0
    lat1, lon1 = radians(start.lat), radians(start.lng)
    lat2, lon2 = radians(end.lat), radians(end.lng)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * earth_radius_km * atan2(sqrt(a), sqrt(1 - a))


def route_distance_km(sequence: list[Waypoint]) -> float:
    return sum(haversine_distance_km(sequence[index], sequence[index + 1]) for index in range(len(sequence) - 1))


def passenger_distance_km(sequence: list[Waypoint], ride_drop_index: int) -> float:
    return route_distance_km(sequence[: ride_drop_index + 1])


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_option(
    label: str,
    sequence: list[Waypoint],
    ride_drop_index: int,
    baseline_distance: float,
    baseline_passenger_distance: float,
    parcel_direct_distance: float,
) -> OptionScore:
    total_distance = route_distance_km(sequence)
    passenger_distance = passenger_distance_km(sequence, ride_drop_index)
    extra_distance = max(0.0, total_distance - baseline_distance)
    passenger_delay = max(0.0, passenger_distance - baseline_passenger_distance)
    overlap_distance = max(0.0, parcel_direct_distance - extra_distance)
    extra_time = extra_distance / AVERAGE_SPEED_KMH * 60
    score = clamp(
        68.0 + (overlap_distance * 12.5) - (extra_distance * 7.0) - (passenger_delay * 4.5),
        0.0,
        100.0,
    )

    return OptionScore(
        label=label,
        sequence=sequence,
        total_distance=round(total_distance, 2),
        passenger_distance=round(passenger_distance, 2),
        extra_distance=round(extra_distance, 2),
        passenger_delay=round(passenger_delay, 2),
        overlap_distance=round(overlap_distance, 2),
        extra_time=round(extra_time, 2),
        efficiency_score=round(score, 1),
    )


_RIDE_PICKUP, _RIDE_DROP, _PARCEL_PICKUP, _PARCEL_DROP = range(4)


def enumerate_valid_orderings(
    driver_location: Waypoint,
    ride_pickup: Waypoint,
    ride_drop: Waypoint,
    parcel_pickup: Waypoint,
    parcel_drop: Waypoint,
) -> list[tuple[list[Waypoint], int]]:
    """All sequences of the 4 stops that respect each job's own precedence
    (pickup before its own drop). Of the 4! = 24 permutations, exactly
    4! / (2 * 2) = 6 satisfy both constraints. This is the full combined-route
    search space for a single driver carrying one ride and one parcel at once.

    Returns (sequence, ride_drop_index) pairs. Precedence is checked by
    permuting role indices (0-3) rather than the Waypoint values themselves:
    Waypoint equality is by (name, lat, lng), so if a ride and parcel happen
    to share a pickup or drop location (same name/coordinates — a real case
    with this app's small set of named demo locations), `list.index()` on
    values can't tell the two apart and returns whichever occurrence comes
    first for both checks, silently admitting an invalid ordering. Role
    indices are always distinct, so this is unambiguous regardless of
    whether the underlying coordinates collide.
    """
    stops = [ride_pickup, ride_drop, parcel_pickup, parcel_drop]
    orderings = []
    for roles in permutations(range(4)):
        if roles.index(_RIDE_PICKUP) < roles.index(_RIDE_DROP) and roles.index(_PARCEL_PICKUP) < roles.index(
            _PARCEL_DROP
        ):
            sequence = [driver_location] + [stops[role] for role in roles]
            ride_drop_index = roles.index(_RIDE_DROP) + 1  # +1 for the driver_location prefix
            orderings.append((sequence, ride_drop_index))
    return orderings


def best_combined_extra_distance(
    driver_location: Waypoint,
    ride_pickup: Waypoint,
    ride_drop: Waypoint,
    parcel_pickup: Waypoint,
    parcel_drop: Waypoint,
) -> float:
    """Cheapest extra distance (km) of bundling this parcel onto this ride for
    this driver, minimized over all 6 valid orderings. Used as the assignment
    engine's cost metric — a lighter-weight cousin of optimize_route() that
    skips the full scoring/labeling pass since selection and labeling are
    separate concerns.
    """
    baseline_distance = route_distance_km([driver_location, ride_pickup, ride_drop])
    best_extra = None
    for sequence, _ride_drop_index in enumerate_valid_orderings(
        driver_location, ride_pickup, ride_drop, parcel_pickup, parcel_drop
    ):
        extra = route_distance_km(sequence) - baseline_distance
        if best_extra is None or extra < best_extra:
            best_extra = extra
    return max(0.0, best_extra if best_extra is not None else 0.0)


def optimize_route(
    driver_location: Waypoint,
    ride_pickup: Waypoint,
    ride_drop: Waypoint,
    parcel_pickup: Waypoint,
    parcel_drop: Waypoint,
) -> dict[str, object]:
    baseline_sequence = [driver_location, ride_pickup, ride_drop]
    baseline_distance = route_distance_km(baseline_sequence)
    baseline_passenger_distance = baseline_distance
    parcel_direct_distance = route_distance_km([parcel_pickup, parcel_drop])

    accept_both_candidates = [
        build_option(
            "ACCEPT BOTH",
            sequence,
            ride_drop_index,
            baseline_distance,
            baseline_passenger_distance,
            parcel_direct_distance,
        )
        for sequence, ride_drop_index in enumerate_valid_orderings(
            driver_location, ride_pickup, ride_drop, parcel_pickup, parcel_drop
        )
    ]

    accept_both = max(
        accept_both_candidates,
        key=lambda option: (option.efficiency_score, -option.extra_distance, -option.passenger_delay),
    )
    passenger_first = build_option(
        "PASSENGER FIRST",
        [driver_location, ride_pickup, ride_drop, parcel_pickup, parcel_drop],
        2,  # ride_drop is the 3rd stop in this fixed sequence
        baseline_distance,
        baseline_passenger_distance,
        parcel_direct_distance,
    )
    parcel_first = build_option(
        "PARCEL FIRST",
        [driver_location, parcel_pickup, parcel_drop, ride_pickup, ride_drop],
        4,  # ride_drop is the last stop in this fixed sequence
        baseline_distance,
        baseline_passenger_distance,
        parcel_direct_distance,
    )

    ordered = sorted(
        [accept_both, passenger_first, parcel_first],
        key=lambda option: (option.efficiency_score, -option.extra_distance),
        reverse=True,
    )
    best_option = ordered[0]

    if (
        accept_both.efficiency_score >= ACCEPT_BOTH_MIN_EFFICIENCY_SCORE
        and accept_both.extra_time <= ACCEPT_BOTH_MAX_EXTRA_TIME_MIN
        and accept_both.passenger_delay <= ACCEPT_BOTH_MAX_PASSENGER_DELAY_KM
    ):
        chosen = accept_both
    elif passenger_first.efficiency_score >= parcel_first.efficiency_score and passenger_first.efficiency_score >= 55:
        chosen = passenger_first
    elif parcel_first.efficiency_score >= 55:
        chosen = parcel_first
    else:
        chosen = OptionScore(
            label="REJECT COMBINATION",
            sequence=baseline_sequence,
            total_distance=round(baseline_distance, 2),
            passenger_distance=round(baseline_passenger_distance, 2),
            extra_distance=round(best_option.extra_distance, 2),
            passenger_delay=round(best_option.passenger_delay, 2),
            overlap_distance=round(best_option.overlap_distance, 2),
            extra_time=round(best_option.extra_time, 2),
            efficiency_score=round(best_option.efficiency_score, 1),
        )

    constraints = [
        {
            "key": "efficiency_score",
            "label": "Efficiency score",
            "actual": accept_both.efficiency_score,
            "threshold": ACCEPT_BOTH_MIN_EFFICIENCY_SCORE,
            "comparison": "gte",
            "passed": accept_both.efficiency_score >= ACCEPT_BOTH_MIN_EFFICIENCY_SCORE,
        },
        {
            "key": "extra_time",
            "label": "Extra travel time",
            "actual": accept_both.extra_time,
            "threshold": ACCEPT_BOTH_MAX_EXTRA_TIME_MIN,
            "comparison": "lte",
            "passed": accept_both.extra_time <= ACCEPT_BOTH_MAX_EXTRA_TIME_MIN,
        },
        {
            "key": "passenger_delay",
            "label": "Passenger delay",
            "actual": accept_both.passenger_delay,
            "threshold": ACCEPT_BOTH_MAX_PASSENGER_DELAY_KM,
            "comparison": "lte",
            "passed": accept_both.passenger_delay <= ACCEPT_BOTH_MAX_PASSENGER_DELAY_KM,
        },
    ]

    return {
        "efficiency_score": chosen.efficiency_score,
        "extra_distance": chosen.extra_distance,
        "extra_time": chosen.extra_time,
        "overlap_distance": chosen.overlap_distance,
        "recommendation": chosen.label,
        "optimized_route": [asdict(point) for point in chosen.sequence],
        "candidate_options": {
            "accept_both": asdict(accept_both),
            "passenger_first": asdict(passenger_first),
            "parcel_first": asdict(parcel_first),
        },
        # Explains WHY the recommendation came out the way it did, regardless
        # of which option was actually chosen: the ACCEPT BOTH candidate's
        # own numbers and constraint pass/fail, so a captain can see what the
        # combined route would have looked like even when a different (or
        # no) option was selected instead.
        "accept_both_analysis": {
            "passenger_baseline_distance": round(baseline_distance, 2),
            "combined_route_distance": accept_both.total_distance,
            "extra_distance": accept_both.extra_distance,
            "extra_time": accept_both.extra_time,
            "passenger_delay": accept_both.passenger_delay,
            "overlap_distance": accept_both.overlap_distance,
            "efficiency_score": accept_both.efficiency_score,
            "route_sequence": [asdict(point) for point in accept_both.sequence],
            "constraints": constraints,
            "all_constraints_passed": all(constraint["passed"] for constraint in constraints),
        },
    }
