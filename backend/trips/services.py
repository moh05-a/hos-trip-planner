"""External services: geocoding (Photon -> Nominatim) and routing (OSRM -> OpenRouteService).

All of these are free. OSRM's and Photon's public servers need no API key; an
OpenRouteService key (env ORS_API_KEY) is optional and used as a fallback router.
"""
from __future__ import annotations

import logging
import os

import requests
from django.core.cache import cache

from .geo import haversine_mi, nearest_city

log = logging.getLogger(__name__)

USER_AGENT = os.environ.get("HTTP_USER_AGENT", "spotter-eld-trip-planner/1.0 (assessment demo)")
TIMEOUT = 15
METERS_PER_MILE = 1609.344

OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
PHOTON_URL = os.environ.get("PHOTON_URL", "https://photon.komoot.io")
NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
ORS_URL = "https://api.openrouteservice.org"

STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL", "Nova Scotia": "NS", "Ontario": "ON", "Quebec": "QC",
    "Saskatchewan": "SK", "Prince Edward Island": "PE",
}


class ServiceError(Exception):
    pass


def _get(url, params=None, headers=None):
    h = {"User-Agent": USER_AGENT, "Accept-Language": "en"}
    h.update(headers or {})
    r = requests.get(url, params=params, headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _short(city, state, fallback):
    st = STATE_ABBR.get(state or "", state or "")
    if city and st:
        return f"{city}, {st}"
    return city or fallback


# ------------------------------------------------------------------ geocode --
def _photon(q, limit):
    # A location bias pulls short prefixes toward small places near the bias point
    # ("Chi" -> Chicago Avenue, KS), so filter to North America and to places a truck
    # can go instead: no states or counties.
    data = _get(f"{PHOTON_URL}/api/", params={
        "q": q, "limit": limit + 4, "lang": "en", "bbox": "-168,14,-52,72",
        "layer": ["city", "district", "locality", "street", "house", "other"]})
    out = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        if p.get("countrycode") not in ("US", "CA", "MX"):
            continue
        lng, lat = f["geometry"]["coordinates"]
        city = p.get("city") or (p.get("name") if p.get("type") in ("city", "town", "village") else None)
        parts = [p.get("name"), p.get("street") and f"{p.get('housenumber', '')} {p['street']}".strip(),
                 p.get("city") if p.get("city") != p.get("name") else None, p.get("state"), p.get("countrycode")]
        label = ", ".join(dict.fromkeys(x for x in parts if x))
        if any(o["label"] == label for o in out):
            continue
        out.append({"label": label, "short": _short(city, p.get("state"), p.get("name") or label),
                    "lat": lat, "lng": lng})
    return out[:limit]


def _nominatim(q, limit):
    data = _get(f"{NOMINATIM_URL}/search", params={
        "q": q, "format": "jsonv2", "addressdetails": 1, "limit": limit, "countrycodes": "us,ca,mx"})
    out = []
    for r in data:
        a = r.get("address", {})
        city = a.get("city") or a.get("town") or a.get("village") or a.get("hamlet") or a.get("county")
        out.append({"label": r.get("display_name"), "short": _short(city, a.get("state"), r.get("name")),
                    "lat": float(r["lat"]), "lng": float(r["lon"])})
    return out


def geocode(q: str, limit: int = 6) -> list[dict]:
    q = (q or "").strip()
    if len(q) < 2:
        return []
    key = f"geo:{q.lower()}:{limit}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    results = []
    failures = 0
    for fn in (_photon, _nominatim):
        try:
            results = fn(q, limit)
            if results:
                break
        except Exception as e:  # pragma: no cover - network
            failures += 1
            log.warning("geocoder %s failed: %s", fn.__name__, e)
    if failures == 2:
        raise ServiceError("Address search is unavailable right now. Pick a suggestion or try again in a minute.")
    for r in results:  # make sure every short label looks like "City, ST"
        if "," not in r["short"]:
            r["short"] = nearest_city(r["lat"], r["lng"], 25) or r["short"]
    cache.set(key, results, 60 * 60 * 24)
    return results


# ------------------------------------------------------------------- routing --
def _osrm(a, b):
    coords = f"{a['lng']},{a['lat']};{b['lng']},{b['lat']}"
    data = _get(f"{OSRM_URL}/route/v1/driving/{coords}",
                params={"overview": "full", "geometries": "geojson", "steps": "false"})
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ServiceError(data.get("message") or "No route found")
    r = data["routes"][0]
    pts = [[lat, lng] for lng, lat in r["geometry"]["coordinates"]]
    return {"distance_mi": r["distance"] / METERS_PER_MILE, "duration_hr": r["duration"] / 3600,
            "geometry": pts, "source": "OSRM"}


def _ors(a, b):
    key = os.environ.get("ORS_API_KEY")
    if not key:
        raise ServiceError("ORS_API_KEY not configured")
    r = requests.post(f"{ORS_URL}/v2/directions/driving-hgv/geojson",
                      json={"coordinates": [[a["lng"], a["lat"]], [b["lng"], b["lat"]]]},
                      headers={"Authorization": key, "User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    feat = r.json()["features"][0]
    s = feat["properties"]["summary"]
    pts = [[lat, lng] for lng, lat in feat["geometry"]["coordinates"]]
    return {"distance_mi": s["distance"] / METERS_PER_MILE, "duration_hr": s["duration"] / 3600,
            "geometry": pts, "source": "OpenRouteService (HGV)"}


def _estimate(a, b):
    """Last-resort fallback so the planner still works if the public routers are down."""
    d = haversine_mi(a["lat"], a["lng"], b["lat"], b["lng"]) * 1.2
    n = 50
    pts = [[a["lat"] + (b["lat"] - a["lat"]) * i / n, a["lng"] + (b["lng"] - a["lng"]) * i / n]
           for i in range(n + 1)]
    return {"distance_mi": d, "duration_hr": d / 55.0, "geometry": pts, "source": "Estimated (straight line)"}


def route(a: dict, b: dict) -> dict:
    key = f"route:{a['lat']:.4f},{a['lng']:.4f}:{b['lat']:.4f},{b['lng']:.4f}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    if haversine_mi(a["lat"], a["lng"], b["lat"], b["lng"]) < 0.05:
        res = {"distance_mi": 0.0, "duration_hr": 0.0, "geometry": [[a["lat"], a["lng"]], [b["lat"], b["lng"]]],
               "source": "same location"}
        return res
    errors = []
    for fn in (_osrm, _ors):
        try:
            res = fn(a, b)
            cache.set(key, res, 60 * 60 * 6)
            return res
        except Exception as e:  # pragma: no cover - network
            errors.append(f"{fn.__name__}: {e}")
            log.warning("router %s failed: %s", fn.__name__, e)
    if os.environ.get("ALLOW_ESTIMATED_ROUTES", "1") == "1":
        res = _estimate(a, b)
        res["warning"] = "Routing service unavailable - distances estimated. " + "; ".join(errors)
        return res
    raise ServiceError("Could not compute a route: " + "; ".join(errors))
