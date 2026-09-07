from __future__ import annotations

from dataclasses import dataclass

DEFAULT_CELL_SIZE_DEG = 0.02  # roughly ~2.2km at this latitude, tunable per deployment


@dataclass(frozen=True)
class GridPoint:
    id: int
    lat: float
    lng: float


def cell_key(lat: float, lng: float, cell_size_deg: float = DEFAULT_CELL_SIZE_DEG) -> tuple[int, int]:
    return (int(lat // cell_size_deg), int(lng // cell_size_deg))


def build_grid_index(
    points: list[GridPoint],
    cell_size_deg: float = DEFAULT_CELL_SIZE_DEG,
) -> dict[tuple[int, int], list[GridPoint]]:
    index: dict[tuple[int, int], list[GridPoint]] = {}
    for point in points:
        key = cell_key(point.lat, point.lng, cell_size_deg)
        index.setdefault(key, []).append(point)
    return index


def nearby(
    index: dict[tuple[int, int], list[GridPoint]],
    origin_lat: float,
    origin_lng: float,
    cell_size_deg: float = DEFAULT_CELL_SIZE_DEG,
) -> list[GridPoint]:
    """Returns points from the origin's cell and its 8 neighbors (3x3 block).

    This is the same principle behind geohash/H3 bucketing, simplified to a
    fixed-size uniform grid: O(1) bucket lookup instead of scanning every
    candidate, at the cost of a coarser (but tunable) neighbor radius.
    """
    origin_col, origin_row = cell_key(origin_lat, origin_lng, cell_size_deg)
    results: list[GridPoint] = []
    for d_col in (-1, 0, 1):
        for d_row in (-1, 0, 1):
            results.extend(index.get((origin_col + d_col, origin_row + d_row), []))
    return results
