from unittest import mock

from django.test import SimpleTestCase


def fake_route(a, b):
    from trips.geo import haversine_mi
    d = haversine_mi(a["lat"], a["lng"], b["lat"], b["lng"]) * 1.15
    n = 20
    pts = [[a["lat"] + (b["lat"] - a["lat"]) * i / n, a["lng"] + (b["lng"] - a["lng"]) * i / n] for i in range(n + 1)]
    return {"distance_mi": d, "duration_hr": d / 60, "geometry": pts, "source": "test"}


CHI = {"label": "Chicago, Illinois, USA", "short": "Chicago, IL", "lat": 41.8781, "lng": -87.6298}
STL = {"label": "St. Louis, Missouri, USA", "short": "St. Louis, MO", "lat": 38.627, "lng": -90.1994}
LA = {"label": "Los Angeles, California, USA", "short": "Los Angeles, CA", "lat": 34.0522, "lng": -118.2437}


@mock.patch("trips.services.route", side_effect=fake_route)
class PlanTripAPITests(SimpleTestCase):
    def post(self, **over):
        body = {"current_location": CHI, "pickup_location": STL, "dropoff_location": LA,
                "current_cycle_used": 10, "start_time": "2026-10-05T06:00"}
        body.update(over)
        return self.client.post("/api/plan-trip/", body, content_type="application/json")

    def test_plan_trip(self, _route):
        r = self.post()
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertGreater(data["summary"]["total_miles"], 1800)
        self.assertGreaterEqual(len(data["logs"]), 3)
        self.assertEqual(data["stops"][0]["type"], "start")
        types = [s["type"] for s in data["stops"]]
        self.assertIn("pickup", types)
        self.assertEqual(types[-1], "dropoff")
        self.assertIn("fuel", types)
        self.assertIn("rest", types)
        # labels come from the offline city table
        rest = next(s for s in data["stops"] if s["type"] == "rest")
        self.assertRegex(rest["short"], r", [A-Z]{2}$")
        for log in data["logs"]:
            self.assertAlmostEqual(sum(log["totals"].values()), 24, places=1)

    def test_validation(self, _route):
        r = self.post(current_cycle_used=80)
        self.assertEqual(r.status_code, 400)
        self.assertIn("current_cycle_used", r.json()["errors"])
        r = self.post(pickup_location="")
        self.assertEqual(r.status_code, 400)

    @mock.patch("trips.services.geocode", return_value=[])
    def test_unknown_place(self, _geo, _route):
        r = self.post(pickup_location="zzzz nowhere")
        self.assertEqual(r.status_code, 422)

    def test_health(self, _route):
        self.assertEqual(self.client.get("/api/health/").json(), {"status": "ok"})


class GeoTests(SimpleTestCase):
    def test_nearest_city(self):
        from trips.geo import nearest_city
        self.assertEqual(nearest_city(41.8781, -87.6298), "Chicago, IL")
        self.assertEqual(nearest_city(34.0522, -118.2437), "Los Angeles, CA")
        self.assertIsNone(nearest_city(0, -150))
