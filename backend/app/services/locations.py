from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KnownLocation:
    name: str
    lat: float
    lng: float


KNOWN_LOCATIONS = {
    "vit": KnownLocation("VIT Vellore", 12.9692, 79.1559),
    "vit vellore": KnownLocation("VIT Vellore", 12.9692, 79.1559),
    "cmc": KnownLocation("CMC Hospital", 12.9259, 79.1356),
    "cmc hospital": KnownLocation("CMC Hospital", 12.9259, 79.1356),
    "katpadi": KnownLocation("Katpadi Railway Station", 12.9682, 79.1456),
    "katpadi railway station": KnownLocation("Katpadi Railway Station", 12.9682, 79.1456),
    "gandhi nagar": KnownLocation("Gandhi Nagar", 12.9448, 79.1324),
    "vellore fort": KnownLocation("Vellore Fort", 12.9165, 79.1325),
    "bagayam": KnownLocation("Bagayam", 12.8876, 79.0907),
    "ranipet": KnownLocation("Ranipet", 12.9278, 79.3332),
}


def normalize_location_key(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def resolve_location(value: str) -> KnownLocation:
    key = normalize_location_key(value)
    location = KNOWN_LOCATIONS.get(key)
    if not location:
        raise ValueError(
            f"Unknown location '{value}'. Try VIT Vellore, CMC Hospital, Katpadi Railway Station, or Gandhi Nagar."
        )
    return location


def resolve_location_input(
    value: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> KnownLocation:
    if lat is not None and lng is not None:
        return KnownLocation(name=value.strip() or "Selected Location", lat=lat, lng=lng)
    return resolve_location(value)
