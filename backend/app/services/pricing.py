from __future__ import annotations

from app.models import Parcel, Ride
from app.services.route_optimizer import Waypoint, route_distance_km

PRIORITY_MULTIPLIERS = {
    "Low": 1.0,
    "Medium": 1.05,
    "High": 1.12,
    "Urgent": 1.2,
}


def _ride_distance_km(ride: Ride) -> float:
    return route_distance_km(
        [
            Waypoint(ride.pickup_name, ride.pickup_lat, ride.pickup_lng),
            Waypoint(ride.drop_name, ride.drop_lat, ride.drop_lng),
        ]
    )


def _parcel_distance_km(parcel: Parcel) -> float:
    return route_distance_km(
        [
            Waypoint(parcel.pickup_name, parcel.pickup_lat, parcel.pickup_lng),
            Waypoint(parcel.drop_name, parcel.drop_lat, parcel.drop_lng),
        ]
    )


def estimate_ride_base_price(ride: Ride) -> float:
    ride_distance = _ride_distance_km(ride)
    return round(75.0 + (ride_distance * 14.0) + max(0, ride.passenger_count - 1) * 6.0, 2)


def estimate_parcel_base_price(parcel: Parcel) -> float:
    parcel_distance = _parcel_distance_km(parcel)
    return round(
        (38.0 + (parcel_distance * 9.0) + (parcel.parcel_weight * 1.75))
        * PRIORITY_MULTIPLIERS.get(parcel.priority, 1.0),
        2,
    )


def estimate_customer_pricing(
    ride: Ride,
    parcel: Parcel,
    overlap_distance: float,
    extra_time: float,
) -> dict[str, float]:
    ride_base = estimate_ride_base_price(ride)
    parcel_base = estimate_parcel_base_price(parcel)

    estimated_savings = max(18.0, (overlap_distance * 11.5) + max(0.0, (12.0 - extra_time) * 2.8))
    ride_discount = estimated_savings * 0.58
    parcel_discount = estimated_savings * 0.42

    ride_base_price = round(ride_base, 2)
    parcel_base_price = round(parcel_base, 2)
    ride_customer_price = max(60.0, ride_base - ride_discount)
    parcel_customer_price = max(30.0, parcel_base - parcel_discount)
    combined_customer_total = ride_customer_price + parcel_customer_price

    return {
        "ride_base_price": ride_base_price,
        "parcel_base_price": parcel_base_price,
        "ride_customer_price": round(ride_customer_price, 2),
        "parcel_customer_price": round(parcel_customer_price, 2),
        "combined_customer_total": round(combined_customer_total, 2),
        "estimated_customer_savings": round((ride_base_price + parcel_base_price) - combined_customer_total, 2),
    }
