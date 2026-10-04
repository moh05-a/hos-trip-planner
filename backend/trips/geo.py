"""Geometry helpers: distance along a route polyline and offline nearest-city lookup.

The nearest-city lookup uses a bundled GeoNames extract (cities with population >= 1000
in the US, Canada and Mexico) so that every duty-status change on the log can be
labelled "City, ST" without hammering a reverse-geocoding API.
"""
from __future__ import annotations

import bisect
import csv
import math
from functools import lru_cache
from pathlib import Path

EARTH_RADIUS_MI = 3958.8
DATA_FILE = Path(__file__).resolve().parent / "data" / "cities_na.csv"


def haversine_mi(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(a)))


# ------------------------------------------------------------------ cities ---
@lru_cache(maxsize=1)
def _city_grid():
    grid: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        for lat, lng, name, st in csv.reader(f):
            lat, lng = float(lat), float(lng)
            grid.setdefault((int(math.floor(lat)), int(math.floor(lng))), []).append(
                (lat, lng, f"{name}, {st}"))
    return grid


def nearest_city(lat: float, lng: float, max_mi: float = 60.0) -> str | None:
    grid = _city_grid()
    ci, cj = int(math.floor(lat)), int(math.floor(lng))
    best, best_d = None, max_mi
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for clat, clng, label in grid.get((ci + di, cj + dj), ()):
                d = haversine_mi(lat, lng, clat, clng)
                if d < best_d:
                    best, best_d = label, d
    return best


# ----------------------------------------------------------------- polyline ---
class RoutePath:
    """A polyline ([lat, lng] points) parameterised by *route* miles.

    Straight-line point-to-point distances are scaled so the total equals the routing
    engine's reported distance, so that mile N on the planner maps onto the polyline.
    """

    def __init__(self, points: list[list[float]], route_miles: float):
        if len(points) < 2:
            raise ValueError("Route geometry needs at least 2 points")
        self.points = points
        cum = [0.0]
        for (a, b), (c, d) in zip(points, points[1:]):
            cum.append(cum[-1] + haversine_mi(a, b, c, d))
        raw = cum[-1] or 1.0
        scale = (route_miles / raw) if route_miles > 0 else 1.0
        self.cum = [x * scale for x in cum]
        self.length = self.cum[-1]

    def point_at(self, mile: float) -> tuple[float, float]:
        mile = max(0.0, min(mile, self.length))
        i = bisect.bisect_right(self.cum, mile) - 1
        i = max(0, min(i, len(self.points) - 2))
        seg = self.cum[i + 1] - self.cum[i]
        f = 0.0 if seg <= 0 else (mile - self.cum[i]) / seg
        (a, b), (c, d) = self.points[i], self.points[i + 1]
        return a + (c - a) * f, b + (d - b) * f


class TripLocator:
    """Maps a trip mile (0 = current location) to lat/lng and a "City, ST" label."""

    def __init__(self, paths: list[RoutePath], anchors: list[tuple[float, str]]):
        self.paths = paths
        self.offsets = []
        acc = 0.0
        for p in paths:
            self.offsets.append(acc)
            acc += p.length
        self.total = acc
        # anchors: (mile, label) for the user's three locations - preferred when close
        self.anchors = anchors

    def __call__(self, mile: float) -> dict:
        idx = 0
        for k, off in enumerate(self.offsets):
            if mile >= off - 1e-6:
                idx = k
        lat, lng = self.paths[idx].point_at(mile - self.offsets[idx])
        for amile, alabel in self.anchors:
            if abs(amile - mile) < 0.5:
                return {"lat": lat, "lng": lng, "label": alabel}
        label = nearest_city(lat, lng) or f"{lat:.3f}, {lng:.3f}"
        return {"lat": lat, "lng": lng, "label": label}


def simplify(points: list[list[float]], max_points: int = 1500) -> list[list[float]]:
    if len(points) <= max_points:
        return [[round(a, 5), round(b, 5)] for a, b in points]
    step = len(points) / max_points
    out = [points[int(i * step)] for i in range(max_points)]
    out.append(points[-1])
    return [[round(a, 5), round(b, 5)] for a, b in out]
