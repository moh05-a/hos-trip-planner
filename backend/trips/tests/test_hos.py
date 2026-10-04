from datetime import datetime

from django.test import SimpleTestCase

from trips.hos import (D, OFF, ON, SB, HOSPlanner, Leg, build_daily_logs)


def plan(leg1, leg2, cycle=0.0, speed=50.0):
    legs = [Leg(leg1, leg1 / speed, "A", "B"), Leg(leg2, leg2 / speed, "B", "C")]
    p = HOSPlanner(legs, cycle)
    return p, p.plan()


def check_hos_compliance(tc, events, start_cycle=0.0):
    """Walk the events and assert every federal limit holds."""
    drive = 0.0
    since_break = 0.0
    window_start = None
    cycle = start_cycle
    off_run = 10.0
    nd_run = 0.0
    for e in events:
        if e.status in (OFF, SB):
            off_run += e.duration
            if off_run >= 10 - 1e-6:
                drive, since_break, window_start = 0.0, 0.0, None
            if off_run >= 34 - 1e-6:
                cycle = 0.0
        else:
            off_run = 0.0
            if window_start is None:
                window_start = e.start
        if e.status == D:
            nd_run = 0.0
            drive += e.duration
            since_break += e.duration
            tc.assertLessEqual(drive, 11 + 1e-6, "11-hour limit broken")
            tc.assertLessEqual(e.end - window_start, 14 + 1e-6, "drove after 14-hour window")
            tc.assertLessEqual(since_break, 8 + 1e-6, "missing 30-minute break")
            tc.assertLessEqual(cycle + e.duration, 70 + 1e-6, "70-hour limit broken")
        else:
            nd_run += e.duration
            if nd_run >= 0.5 - 1e-6:
                since_break = 0.0
        if e.status in (ON, D):
            cycle += e.duration


class HOSRuleTests(SimpleTestCase):
    def test_short_trip_has_pickup_and_dropoff_only(self):
        p, ev = plan(100, 200)
        kinds = [e.kind for e in ev]
        self.assertEqual(kinds, ["drive", "pickup", "drive", "dropoff"])
        self.assertAlmostEqual(ev[1].duration, 1.0)
        self.assertAlmostEqual(ev[-1].duration, 1.0)

    def test_30_minute_break_after_8_hours_driving(self):
        # 450 mi at 50 mph = 9 h of driving after pickup
        p, ev = plan(1, 450)
        breaks = [e for e in ev if e.kind == "break"]
        self.assertEqual(len(breaks), 1)
        self.assertAlmostEqual(breaks[0].duration, 0.5)
        driving_before = sum(e.duration for e in ev if e.status == D and e.end <= breaks[0].start + 1e-9
                             and e.start >= ev[1].end - 1e-9)
        self.assertAlmostEqual(driving_before, 8.0)

    def test_pickup_counts_as_break(self):
        # 6 h drive, 1 h pickup (on-duty, not driving) resets the 8-hour clock
        p, ev = plan(300, 250)
        self.assertFalse(any(e.kind == "break" for e in ev))

    def test_11_hour_limit_triggers_10_hour_rest(self):
        p, ev = plan(1, 1000)
        rests = [e for e in ev if e.kind == "rest"]
        self.assertGreaterEqual(len(rests), 1)
        self.assertAlmostEqual(rests[0].duration, 10.0)
        self.assertEqual(rests[0].status, SB)
        check_hos_compliance(self, ev)

    def test_fuel_every_1000_miles(self):
        p, ev = plan(500, 2600)
        fuels = [e for e in ev if e.kind == "fuel"]
        self.assertEqual(len(fuels), 3)  # at 1000, 2000, 3000 mi
        for f, mile in zip(fuels, (1000, 2000, 3000)):
            self.assertAlmostEqual(f.start_mile, mile, places=4)
            self.assertAlmostEqual(f.duration, 0.5)
        check_hos_compliance(self, ev)

    def test_cycle_limit_forces_34_hour_restart(self):
        p, ev = plan(100, 600, cycle=65)
        restarts = [e for e in ev if e.kind == "restart"]
        self.assertEqual(len(restarts), 1)
        self.assertAlmostEqual(restarts[0].duration, 34)
        check_hos_compliance(self, ev, start_cycle=65)

    def test_full_cycle_restarts_before_driving(self):
        p, ev = plan(100, 100, cycle=70)
        self.assertEqual(ev[0].kind, "restart")
        check_hos_compliance(self, ev, start_cycle=70)

    def test_long_trips_are_always_compliant(self):
        for cycle in (0, 12.5, 33, 50, 69):
            for l1, l2 in ((50, 2800), (900, 1900), (1500, 3000), (10, 120)):
                with self.subTest(cycle=cycle, l1=l1, l2=l2):
                    p, ev = plan(l1, l2, cycle=cycle, speed=58.0)
                    check_hos_compliance(self, ev, start_cycle=cycle)
                    driven = sum(e.end_mile - e.start_mile for e in ev if e.status == D)
                    self.assertAlmostEqual(driven, l1 + l2, places=3)

    def test_invalid_cycle(self):
        with self.assertRaises(ValueError):
            HOSPlanner([Leg(1, 1), Leg(1, 1)], 71)


class DailyLogTests(SimpleTestCase):
    def logs_for(self, l1, l2, cycle=0, start=datetime(2026, 10, 5, 7, 30)):
        p, ev = plan(l1, l2, cycle=cycle)
        return ev, build_daily_logs(ev, start, cycle, lambda m: {"label": f"mi {m:.0f}"},
                                    {"current": "Start"})["logs"]

    def test_every_sheet_totals_24_hours_and_is_continuous(self):
        ev, logs = self.logs_for(400, 2400, cycle=30)
        self.assertGreater(len(logs), 2)
        for log in logs:
            self.assertAlmostEqual(sum(log["totals"].values()), 24.0, places=2)
            segs = log["segments"]
            self.assertAlmostEqual(segs[0]["start"], 0.0)
            self.assertAlmostEqual(segs[-1]["end"], 24.0)
            for a, b in zip(segs, segs[1:]):
                self.assertAlmostEqual(a["end"], b["start"], places=4)
                self.assertNotEqual(a["status"], b["status"])  # merged

    def test_first_day_is_off_duty_until_start(self):
        ev, logs = self.logs_for(100, 100)
        self.assertEqual(logs[0]["segments"][0]["status"], OFF)
        self.assertAlmostEqual(logs[0]["segments"][0]["end"], 7.5)

    def test_daily_miles_sum_to_trip(self):
        ev, logs = self.logs_for(321, 1789)
        self.assertAlmostEqual(sum(l["miles"] for l in logs), 2110, delta=0.5)

    def test_remarks_on_every_status_change(self):
        ev, logs = self.logs_for(100, 900)
        for log in logs:
            starts = [s["start"] for s in log["segments"] if s["start"] > 0]
            remark_times = [r["time"] for r in log["remarks"]]
            for s in starts:
                self.assertTrue(any(abs(s - t) < 1e-3 for t in remark_times), f"no remark at {s}")

    def test_recap_tracks_cycle(self):
        ev, logs = self.logs_for(100, 100, cycle=40)
        on = sum(e.duration for e in ev if e.status in (ON, D))
        self.assertAlmostEqual(logs[-1]["recap"]["cycle_total"], 40 + on, places=2)
        self.assertAlmostEqual(logs[-1]["recap"]["available_tomorrow"], 70 - 40 - on, places=2)
