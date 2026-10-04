# HOS Trip Planner

A Django + React app that plans a truck trip under the FMCSA Hours of Service rules. You enter where the
truck is, the pickup, the drop-off and how many hours of the 70-hour cycle are already used. The app returns:

- **a route map** with every required stop: fuel, 30-minute breaks, 10-hour rests and 34-hour restarts
- **filled-in Driver's Daily Log sheets**, one per calendar day, drawn like the paper form: the duty-status line on the
  24-hour grid, the total hours on each line, remarks (city and state at each change of duty status) and the 70-hour recap

## How the trip is planned

The scheduler lives in [`backend/trips/hos.py`](backend/trips/hos.py). It is a small simulation that steps forward
through the trip and, before every stretch of driving, works out how long the driver may legally keep going:

```
can_drive = min(11h - driving since last 10h rest,
                14h - time since coming on duty,
                8h  - driving since last 30-min interruption,
                70h - hours used in the cycle)
```

When `can_drive` reaches zero it inserts the right rest. A 34-hour restart if the 70-hour cycle is used up,
otherwise a 10-hour sleeper-berth rest if the 11- or 14-hour limit is reached, otherwise a 30-minute break.
Fuel stops are inserted every 1,000 miles.

| Rule / assumption | How it is applied |
|---|---|
| 11-hour driving limit | 10 consecutive hours off (sleeper berth) after 11 h of driving |
| 14-hour window | No driving after the 14th hour on duty. On-duty work such as unloading may continue |
| 30-minute break | After 8 h of driving. Any 30 min not driving counts (2020 rule), so fuel stops and pickup reset it |
| 70 h / 8 days | Starts from *Current cycle used*. A 34-hour restart resets it to 0 |
| Fuel | 30 min on duty, at least every 1,000 miles |
| Pickup / drop-off | 1 hour on duty (not driving) each |
| Start of trip | Driver is rested (fresh 11/14 h clocks). Off duty from midnight until departure |

The event list is then cut at midnight into daily logs (`build_daily_logs`). Every sheet is checked by tests to
cover exactly 24 hours.

**Recap note:** the app only knows the *total* hours already used, not the day-by-day history. So recap lines A and C
assume those hours stay inside the 8-day window for the whole trip, which is the conservative reading.

## Map and location data (all free, no API key needed)

| Purpose | Service |
|---|---|
| Address search / autocomplete | [Photon](https://photon.komoot.io) (OpenStreetMap), with [Nominatim](https://nominatim.org) as fallback |
| Routing | [OSRM](https://project-osrm.org) public server. Optional: set `ORS_API_KEY` to fall back to OpenRouteService's truck (HGV) profile |
| Map tiles | OpenStreetMap standard tiles, drawn with Leaflet |
| City names for log remarks | Bundled GeoNames extract (US/CA/MX towns), looked up offline so every stop gets a "City, ST" label without extra API calls |

If every routing service is down, the API falls back to a straight-line estimate and the UI says so.

## Project layout

```
backend/                 Django 5/6 + Django REST Framework (stateless, no database)
  trips/hos.py           HOS scheduler + daily log builder   <- the core logic
  trips/planner.py       geocode -> route -> plan -> stops/logs JSON
  trips/services.py      Photon / Nominatim / OSRM / ORS clients with caching
  trips/geo.py           polyline maths, nearest-city lookup
  trips/tests/           unit tests for every rule and the API
frontend/                React 19 + Vite + react-leaflet
  src/components/LogSheet.jsx   SVG drawing of the paper daily log
  src/components/RouteMap.jsx   route, stop markers and popups
```

## API

`POST /api/plan-trip/`

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": { "label": "St. Louis, MO", "lat": 38.627, "lng": -90.1994 },
  "dropoff_location": "Los Angeles, CA",
  "current_cycle_used": 22,
  "start_time": "2026-10-05T06:00"
}
```

Locations can be free text or `{label, lat, lng}`. The response contains `summary`, `route.legs[].geometry`,
`stops[]`, `events[]` (the full duty-status timeline) and `logs[]` (one per day, with `segments`, `totals`,
`remarks` and `recap`).

`GET /api/geocode/?q=dallas` returns place suggestions. `GET /api/health/` is used to wake the server.

## Run locally

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py test          # 19 tests
python manage.py runserver     # http://localhost:8000

# frontend (new terminal)
cd frontend
npm install
cp .env.example .env           # VITE_API_URL=http://localhost:8000
npm run dev                    # http://localhost:5173
```

## Deploy

- **API on Render (free):** New → Blueprint, pick this repo. Render reads [`render.yaml`](render.yaml).
  Check `https://<service>.onrender.com/api/health/`, then run `python backend/smoke_test.py https://<service>.onrender.com`.
- **Frontend on Vercel:** root directory `frontend`, framework preset Vite,
  environment variable `VITE_API_URL=https://<service>.onrender.com` (no trailing slash).

CORS already allows any `https://*.vercel.app` origin.
