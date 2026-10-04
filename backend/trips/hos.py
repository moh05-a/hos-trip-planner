"""
Hours-of-Service trip planner (FMCSA 49 CFR Part 395, property-carrying driver).

Rules modelled
--------------
* 11-hour driving limit           - max 11 h driving after 10 consecutive hours off duty
* 14-hour driving window          - no driving after the 14th hour since coming on duty
                                    (on-duty, non-driving work is still allowed after it)
* 30-minute break                 - required once 8 cumulative hours of driving are reached
                                    without a 30-minute interruption. Any non-driving period
                                    (off duty, sleeper berth or on duty not driving) of >= 30
                                    consecutive minutes satisfies it (2020 rule).
* 70-hour / 8-day limit           - no driving once 70 on-duty hours are used in the cycle
* 34-hour restart                 - 34 consecutive hours off duty resets the cycle to 0
* 10-hour reset                   - 10 consecutive hours off duty / sleeper berth resets the
                                    11- and 14-hour limits

Trip assumptions (from the assessment)
--------------------------------------
* Fuel at least once every 1,000 miles (fuel stop = 30 min on duty, not driving)
* 1 hour on duty for pickup and 1 hour for drop-off
* No adverse driving conditions
* The driver starts the trip fresh for the day (already had >= 10 h off), with
  `cycle_used` hours already consumed in the 70-hour/8-day cycle.

The planner works in *hours since trip start* and in *miles since trip start*.
Turning those into calendar days / log sheets is done in `build_daily_logs`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Callable, Optional

# Duty statuses (the four lines of the log grid)
OFF = "OFF"   # 1. Off duty
SB = "SB"     # 2. Sleeper berth
D = "D"       # 3. Driving
ON = "ON"     # 4. On duty (not driving)
STATUSES = (OFF, SB, D, ON)

MAX_DRIVING = 11.0
DUTY_WINDOW = 14.0
BREAK_AFTER_DRIVING = 8.0
BREAK_LENGTH = 0.5
DAILY_RESET = 10.0
CYCLE_LIMIT = 70.0
RESTART_LENGTH = 34.0
FUEL_INTERVAL_MI = 1000.0
FUEL_STOP_HOURS = 0.5
PICKUP_HOURS = 1.0
DROPOFF_HOURS = 1.0

EPS = 1e-6

Locator = Callable[[float], dict]  # mile -> {"lat", "lng", "label"}


@dataclass
class Leg:
    distance_mi: float
    duration_hr: float
    start_label: str = ""
    end_label: str = ""

    @property
    def speed(self) -> float:
        if self.duration_hr <= 0:
            return 55.0
        return self.distance_mi / self.duration_hr


@dataclass
class Event:
    status: str
    start: float            # hours since trip start
    end: float
    start_mile: float
    end_mile: float
    kind: str               # drive | pickup | dropoff | fuel | break | rest | restart | off
    note: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class PlannerState:
    t: float = 0.0
    mile: float = 0.0
    driving_since_reset: float = 0.0
    window_start: Optional[float] = None
    driving_since_break: float = 0.0
    cycle_used: float = 0.0
    miles_since_fuel: float = 0.0
    non_driving_run: float = 0.0  # length of current consecutive non-driving stretch


class HOSPlanner:
    def __init__(self, legs: list[Leg], cycle_used: float):
        if cycle_used < 0 or cycle_used > CYCLE_LIMIT:
            raise ValueError("Current cycle used must be between 0 and 70 hours.")
        self.legs = legs
        self.s = PlannerState(cycle_used=float(cycle_used))
        self.events: list[Event] = []
        self.restarts = 0

    # ------------------------------------------------------------------ helpers
    def _window_left(self) -> float:
        if self.s.window_start is None:
            return DUTY_WINDOW
        return DUTY_WINDOW - (self.s.t - self.s.window_start)

    def _add(self, status: str, hours: float, kind: str, note: str = "", miles: float = 0.0):
        if hours <= EPS:
            return
        s = self.s
        ev = Event(status, s.t, s.t + hours, s.mile, s.mile + miles, kind, note)
        self.events.append(ev)

        if status in (ON, D) and s.window_start is None:
            s.window_start = s.t
        if status in (ON, D):
            s.cycle_used += hours

        if status == D:
            s.driving_since_reset += hours
            s.driving_since_break += hours
            s.miles_since_fuel += miles
            s.mile += miles
            s.non_driving_run = 0.0
        else:
            s.non_driving_run += hours
            if s.non_driving_run >= BREAK_LENGTH - EPS:
                s.driving_since_break = 0.0
        s.t += hours

        # Resets based on consecutive off-duty time (OFF and SB both count).
        if status in (OFF, SB):
            off_run = self._consecutive_rest()
            if off_run >= DAILY_RESET - EPS:
                s.driving_since_reset = 0.0
                s.window_start = None
                s.driving_since_break = 0.0
            if off_run >= RESTART_LENGTH - EPS:
                s.cycle_used = 0.0

    def _consecutive_rest(self) -> float:
        total = 0.0
        for ev in reversed(self.events):
            if ev.status in (OFF, SB):
                total += ev.duration
            else:
                break
        return total

    # ------------------------------------------------------------- rest logic
    def _take_required_rest(self, need_window_for: float = 0.0):
        """Called when driving is not allowed right now: insert the right rest."""
        s = self.s
        if CYCLE_LIMIT - s.cycle_used <= EPS:
            self.restarts += 1
            self._add(OFF, RESTART_LENGTH, "restart", "34-hour restart (70-hour limit reached)")
        elif MAX_DRIVING - s.driving_since_reset <= EPS or self._window_left() <= EPS:
            reason = "11-hour driving limit" if MAX_DRIVING - s.driving_since_reset <= EPS else "14-hour window"
            self._add(SB, DAILY_RESET, "rest", f"10-hour break ({reason} reached)")
        elif BREAK_AFTER_DRIVING - s.driving_since_break <= EPS:
            self._add(OFF, BREAK_LENGTH, "break", "30-minute break (8 hours of driving)")
        else:  # should not happen, but never loop forever
            self._add(SB, DAILY_RESET, "rest", "10-hour break")

    # ------------------------------------------------------------------- drive
    def _drive_leg(self, leg: Leg, destination: str):
        s = self.s
        remaining = leg.distance_mi
        speed = leg.speed
        while remaining > EPS:
            can_drive = min(
                MAX_DRIVING - s.driving_since_reset,
                self._window_left(),
                BREAK_AFTER_DRIVING - s.driving_since_break,
                CYCLE_LIMIT - s.cycle_used,
            )
            if can_drive <= EPS:
                self._take_required_rest()
                continue
            to_fuel = FUEL_INTERVAL_MI - s.miles_since_fuel
            if to_fuel <= EPS:
                self._add(ON, FUEL_STOP_HOURS, "fuel", "Fuel stop")
                s.miles_since_fuel = 0.0
                continue
            hours = min(can_drive, remaining / speed, to_fuel / speed)
            miles = min(remaining, hours * speed)
            self._add(D, hours, "drive", f"Driving toward {destination}", miles=miles)
            remaining -= miles

    # --------------------------------------------------------------------- run
    def plan(self) -> list[Event]:
        if len(self.legs) != 2:
            raise ValueError("Expected two legs: current->pickup and pickup->dropoff")
        to_pickup, to_dropoff = self.legs
        self._drive_leg(to_pickup, to_pickup.end_label or "pickup")
        self._add(ON, PICKUP_HOURS, "pickup", "Pickup - loading (1 hour)")
        self._drive_leg(to_dropoff, to_dropoff.end_label or "drop-off")
        self._add(ON, DROPOFF_HOURS, "dropoff", "Drop-off - unloading (1 hour)")
        return self.events


# ============================================================== daily logs ===

def _merge(segments: list[dict]) -> list[dict]:
    out: list[dict] = []
    for seg in segments:
        if out and out[-1]["status"] == seg["status"] and abs(out[-1]["end"] - seg["start"]) < EPS:
            out[-1]["end"] = seg["end"]
        else:
            out.append(dict(seg))
    return out


def build_daily_logs(
    events: list[Event],
    start_dt: datetime,
    initial_cycle_used: float,
    locator: Locator,
    labels: dict,
) -> dict:
    """Split the event list into one log sheet per calendar day.

    Times on the sheets are in the home-terminal time of `start_dt` (naive datetime).
    """
    day0 = datetime(start_dt.year, start_dt.month, start_dt.day)
    offset = (start_dt - day0).total_seconds() / 3600.0  # hours from midnight of day 0

    # Absolute timeline in hours since midnight of day 0
    timeline: list[dict] = []
    if offset > EPS:
        timeline.append(dict(status=OFF, start=0.0, end=offset, start_mile=0.0, end_mile=0.0,
                             kind="off", note="Off duty"))
    for ev in events:
        timeline.append(dict(status=ev.status, start=ev.start + offset, end=ev.end + offset,
                             start_mile=ev.start_mile, end_mile=ev.end_mile, kind=ev.kind, note=ev.note))
    trip_end = timeline[-1]["end"]
    n_days = int((trip_end - EPS) // 24) + 1
    last_mile = timeline[-1]["end_mile"]
    timeline.append(dict(status=OFF, start=trip_end, end=n_days * 24.0, start_mile=last_mile,
                         end_mile=last_mile, kind="off", note="Off duty - trip complete"))

    def mile_at(ev: dict, h: float) -> float:
        if ev["end"] - ev["start"] <= EPS:
            return ev["start_mile"]
        f = (h - ev["start"]) / (ev["end"] - ev["start"])
        return ev["start_mile"] + f * (ev["end_mile"] - ev["start_mile"])

    cycle = float(initial_cycle_used)
    off_run = DAILY_RESET  # driver starts rested
    logs = []
    for d in range(n_days):
        lo, hi = d * 24.0, (d + 1) * 24.0
        segs, remarks = [], []
        miles = 0.0
        on_duty_today = 0.0
        prev_key = None
        for ev in timeline:
            a, b = max(ev["start"], lo), min(ev["end"], hi)
            if b - a <= EPS:
                continue
            m_a, m_b = mile_at(ev, a), mile_at(ev, b)
            segs.append(dict(status=ev["status"], start=a - lo, end=b - lo))
            if ev["status"] == D:
                miles += m_b - m_a
            hrs = b - a
            if ev["status"] in (ON, D):
                cycle += hrs
                on_duty_today += hrs
                off_run = 0.0
            else:
                off_run += hrs
                if off_run >= RESTART_LENGTH - EPS:
                    cycle = 0.0
            # Remark (city, state) at every change of duty status / activity that starts this day.
            key = (ev["status"], ev["kind"])
            starts_today = ev["start"] >= lo - EPS
            midnight_off = a - lo <= EPS and ev["kind"] == "off"
            if key != prev_key and starts_today and not midnight_off:
                loc = locator(m_a)
                remarks.append(dict(time=a - lo, status=ev["status"], kind=ev["kind"],
                                    location=loc["label"], note=ev["note"]))
            prev_key = key

        segs = _merge(segs)
        totals = {s: 0.0 for s in STATUSES}
        for sg in segs:
            totals[sg["status"]] += sg["end"] - sg["start"]

        # From / To for the day
        start_mile_day = next(mile_at(ev, max(ev["start"], lo)) for ev in timeline
                              if min(ev["end"], hi) - max(ev["start"], lo) > EPS)
        end_mile_day = [mile_at(ev, min(ev["end"], hi)) for ev in timeline
                        if min(ev["end"], hi) - max(ev["start"], lo) > EPS][-1]
        date = (day0 + timedelta(days=d)).date()
        cycle_r = round(cycle, 2)
        logs.append(dict(
            day=d + 1,
            date=date.isoformat(),
            from_location=locator(start_mile_day)["label"] if d else labels.get("current", ""),
            to_location=locator(end_mile_day)["label"],
            miles=round(miles, 1),
            segments=[{**s, "start": round(s["start"], 4), "end": round(s["end"], 4)} for s in segs],
            totals={k: round(v, 2) for k, v in totals.items()},
            remarks=[{**r, "time": round(r["time"], 4)} for r in remarks],
            recap=dict(
                on_duty_today=round(on_duty_today, 2),
                cycle_total=cycle_r,                       # A / C (prior history assumed within 8 days)
                available_tomorrow=round(max(0.0, CYCLE_LIMIT - cycle), 2),  # B
            ),
        ))
    return dict(logs=logs, timeline_offset=offset, total_days=n_days)


def events_to_dicts(events: list[Event]) -> list[dict]:
    return [asdict(e) for e in events]
