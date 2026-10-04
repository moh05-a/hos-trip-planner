"""Glue: resolve locations -> route legs -> HOS plan -> stops + daily log sheets."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import services
from .geo import RoutePath, TripLocator, simplify
from .hos import D, HOSPlanner, Leg, build_daily_logs, events_to_dicts

STOP_TITLES = {
    "pickup": "Pickup", "dropoff": "Drop-off", "fuel": "Fuel stop", "break": "30-min break",
    "rest": "10-hr rest", "restart": "34-hr restart",
}


def resolve_location(value, field: str) -> dict:
    """Accept {"label", "lat", "lng", "short"} or a free-text string."""
    if isinstance(value, dict) and value.get("lat") is not None and value.get("lng") is not None:
        lat, lng = float(value["lat"]), float(value["lng"])
        label = value.get("label") or f"{lat:.4f}, {lng:.4f}"
        short = value.get("short") or label.split(",")[0]
        return {"label": label, "short": short, "lat": lat, "lng": lng}
    text = value.get("label") if isinstance(value, dict) else value
    results = services.geocode(str(text or ""), limit=1)
    if not results:
        raise services.ServiceError(f"Could not find the {field.replace('_', ' ')} \"{text}\".")
    return results[0]


def plan_trip(current, pickup, dropoff, cycle_used: float, start_time: datetime | None = None) -> dict:
    start_time = start_time or (datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    locs = {
        "current": resolve_location(current, "current_location"),
        "pickup": resolve_location(pickup, "pickup_location"),
        "dropoff": resolve_location(dropoff, "dropoff_location"),
    }
    r1 = services.route(locs["current"], locs["pickup"])
    r2 = services.route(locs["pickup"], locs["dropoff"])

    legs = [
        Leg(r1["distance_mi"], r1["duration_hr"], locs["current"]["short"], locs["pickup"]["short"]),
        Leg(r2["distance_mi"], r2["duration_hr"], locs["pickup"]["short"], locs["dropoff"]["short"]),
    ]
    planner = HOSPlanner(legs, cycle_used)
    events = planner.plan()

    paths = [RoutePath(r1["geometry"], r1["distance_mi"]), RoutePath(r2["geometry"], r2["distance_mi"])]
    total_mi = r1["distance_mi"] + r2["distance_mi"]
    locator = TripLocator(paths, anchors=[
        (0.0, locs["current"]["short"]),
        (r1["distance_mi"], locs["pickup"]["short"]),
        (total_mi, locs["dropoff"]["short"]),
    ])

    def ts(h: float) -> str:
        return (start_time + timedelta(hours=h)).isoformat(timespec="minutes")

    # ---------------------------------------------------------------- stops
    stops = [{
        "type": "start", "title": "Start", "label": locs["current"]["label"],
        "short": locs["current"]["short"], "lat": locs["current"]["lat"], "lng": locs["current"]["lng"],
        "arrive": ts(0), "depart": ts(0), "duration_hr": 0, "mile": 0,
        "note": f"Trip begins - {cycle_used:g} h already used in the 70-hr cycle",
    }]
    for ev in events:
        if ev.status == D:
            continue
        loc = locator(ev.start_mile)
        if ev.kind in ("pickup", "dropoff"):
            src = locs[ev.kind]
            loc = {"lat": src["lat"], "lng": src["lng"], "label": src["short"]}
        stops.append({
            "type": ev.kind, "title": STOP_TITLES.get(ev.kind, ev.kind.title()),
            "label": locs[ev.kind]["label"] if ev.kind in ("pickup", "dropoff") else loc["label"],
            "short": loc["label"], "lat": loc["lat"], "lng": loc["lng"],
            "arrive": ts(ev.start), "depart": ts(ev.end), "duration_hr": round(ev.duration, 2),
            "mile": round(ev.start_mile, 1), "note": ev.note,
        })

    daily = build_daily_logs(events, start_time, cycle_used, locator,
                             {"current": locs["current"]["short"]})

    drive_hours = sum(e.duration for e in events if e.status == D)
    on_duty_hours = sum(e.duration for e in events if e.status in ("ON", D))
    end = events[-1].end
    warnings = [r.get("warning") for r in (r1, r2) if r.get("warning")]

    return {
        "locations": locs,
        "summary": {
            "total_miles": round(total_mi, 1),
            "leg_miles": [round(r1["distance_mi"], 1), round(r2["distance_mi"], 1)],
            "driving_hours": round(drive_hours, 2),
            "on_duty_hours": round(on_duty_hours, 2),
            "trip_hours": round(end, 2),
            "start": ts(0),
            "end": ts(end),
            "days": daily["total_days"],
            "fuel_stops": sum(1 for e in events if e.kind == "fuel"),
            "rest_breaks": sum(1 for e in events if e.kind == "break"),
            "overnight_rests": sum(1 for e in events if e.kind == "rest"),
            "restarts": sum(1 for e in events if e.kind == "restart"),
            "cycle_used_start": cycle_used,
            "cycle_used_end": round(planner.s.cycle_used, 2),
            "route_source": r1["source"] if r1["source"] == r2["source"] else f"{r1['source']} / {r2['source']}",
        },
        "route": {
            "legs": [
                {"from": locs["current"]["short"], "to": locs["pickup"]["short"],
                 "distance_mi": round(r1["distance_mi"], 1), "duration_hr": round(r1["duration_hr"], 2),
                 "geometry": simplify(r1["geometry"])},
                {"from": locs["pickup"]["short"], "to": locs["dropoff"]["short"],
                 "distance_mi": round(r2["distance_mi"], 1), "duration_hr": round(r2["duration_hr"], 2),
                 "geometry": simplify(r2["geometry"])},
            ],
        },
        "stops": stops,
        "events": [{**e, "start_time": ts(e["start"]), "end_time": ts(e["end"])} for e in events_to_dicts(events)],
        "logs": daily["logs"],
        "warnings": warnings,
    }
