"""Smoke-test a deployed API against the real map services.

    python smoke_test.py https://your-api.onrender.com
"""
import json
import sys
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def call(path, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


print("health:", call("/api/health/"))
print("geocode:", [r["short"] for r in call("/api/geocode/?q=Dallas")["results"]][:3])
plan = call("/api/plan-trip/", {"current_location": "Chicago, IL", "pickup_location": "St. Louis, MO",
                                "dropoff_location": "Los Angeles, CA", "current_cycle_used": 22})
s = plan["summary"]
print(f"route: {s['total_miles']} mi via {s['route_source']}, {s['days']} log sheets, warnings={plan['warnings']}")
for log in plan["logs"]:
    print(" ", log["date"], log["totals"], "=", round(sum(log["totals"].values()), 2), "h")
