from __future__ import annotations

from dataclasses import asdict, dataclass
from math import atan2, cos, radians, sin, sqrt

AVERAGE_SPEED_KMH = 28.0


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


def passenger_distance_km(sequence: list[Waypoint], ride_drop: Waypoint) -> float:
    ride_drop_index = sequence.index(ride_drop)
    return route_distance_km(sequence[: ride_drop_index + 1])


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_option(
    label: str,
    sequence: list[Waypoint],
    ride_drop: Waypoint,
    baseline_distance: float,
    baseline_passenger_distance: float,
    parcel_direct_distance: float,
) -> OptionScore:
    total_distance = route_distance_km(sequence)
    passenger_distance = passenger_distance_km(sequence, ride_drop)
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
            [driver_location, ride_pickup, parcel_pickup, parcel_drop, ride_drop],
            ride_drop,
            baseline_distance,
            baseline_passenger_distance,
            parcel_direct_distance,
        ),
        build_option(
            "ACCEPT BOTH",
            [driver_location, ride_pickup, parcel_pickup, ride_drop, parcel_drop],
            ride_drop,
            baseline_distance,
            baseline_passenger_distance,
            parcel_direct_distance,
        ),
        build_option(
            "ACCEPT BOTH",
            [driver_location, parcel_pickup, ride_pickup, parcel_drop, ride_drop],
            ride_drop,
            baseline_distance,
            baseline_passenger_distance,
            parcel_direct_distance,
        ),
    ]

    accept_both = max(
        accept_both_candidates,
        key=lambda option: (option.efficiency_score, -option.extra_distance, -option.passenger_delay),
    )
    passenger_first = build_option(
        "PASSENGER FIRST",
        [driver_location, ride_pickup, ride_drop, parcel_pickup, parcel_drop],
        ride_drop,
        baseline_distance,
        baseline_passenger_distance,
        parcel_direct_distance,
    )
    parcel_first = build_option(
        "PARCEL FIRST",
        [driver_location, parcel_pickup, parcel_drop, ride_pickup, ride_drop],
        ride_drop,
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

    if accept_both.efficiency_score >= 75 and accept_both.extra_time <= 12 and accept_both.passenger_delay <= 3:
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
    }
