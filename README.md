# RouteFusion

RouteFusion is a demo-first MVP that shows how a captain can combine a passenger ride and a parcel delivery into one optimized trip. The latest UI direction uses an Uber-inspired persistent map layout with a shared left-side booking hub for ride requests, parcel requests, and captain decisions.

By default, RouteFusion now runs in transient in-memory mode so every fresh server start begins from zero rides, zero parcels, and zero captain earnings without depending on an external database.

## Architecture

RouteFusion uses a lightweight monorepo split into a React frontend and a FastAPI backend:

- `frontend/` hosts the Vite + React + Tailwind single-page app with navigation for Home, Parcel Request, Ride Request, Captain Corner, Live Map, and Dashboard.
- The booking experience is consolidated into one shared panel, so `Ride Request`, `Parcel Request`, and `Captain Corner` feel like service modes inside the same product surface instead of isolated pages.
- `backend/` hosts the FastAPI API, SQLAlchemy models, JWT auth, demo seeding logic, dashboard aggregation, and the route optimization engine.
- `docs/` contains planning artifacts for the MVP, including the architecture, component tree, wireframes, and deployment notes.

### Runtime flow

1. A demo operator signs in with a demo JWT session.
2. Ride and parcel requests are stored through FastAPI endpoints.
3. Demo mode seeds sample ride, parcel, and driver data.
4. The captain recommendation endpoint runs the route optimizer on the latest open ride and parcel requests.
5. The frontend visualizes the passenger route, parcel route, and optimized route on the Live Map page.
6. The dashboard aggregates request counts, accepted combined trips, average efficiency, and estimated fuel savings.

### Design principles

- Demo-first, not enterprise-first.
- PostgreSQL-ready persistence with a local SQLite fallback for frictionless local development.
- JWT authentication kept intentionally small with a demo login path.
- Matching runs on a real optimal-assignment algorithm (see [System Design](#system-design) below), not a heuristic score — while the per-pair route scoring shown to a captain stays deliberately simple and explainable.
- UI prioritizes clarity, motion, and presentation quality.

## Proposed Folder Structure

```text
routeFusion/
├── README.md
├── docs/
│   └── ui-wireframes.md
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── tests/
│   ├── requirements.txt
│   └── schema.sql
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── lib/
    │   ├── pages/
    │   ├── App.tsx
    │   ├── index.css
    │   ├── main.tsx
    │   └── types.ts
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    └── vite.config.ts
```

## Database Schema

The canonical SQL schema lives in [backend/schema.sql](backend/schema.sql). The core tables are:

- `users`: authentication identity for platform users and operators.
- `drivers`: captain profile and current location.
- `rides`: passenger ride requests and trip metadata.
- `parcels`: parcel delivery requests and trip metadata.
- `route_decisions`: optimizer outputs and captain accept/reject actions.

## API Plan

### Authentication

- `POST /auth/demo-login`
  - Returns a JWT for the demo operator.

### Ride Requests

- `POST /ride`
  - Creates a ride request.
- `GET /ride`
  - Returns recent ride requests for UI refresh and dashboard views.

### Parcel Requests

- `POST /parcel`
  - Creates a parcel request.
- `GET /parcel`
  - Returns recent parcel requests.

### Captain Recommendations

- `GET /captain/recommendations`
  - Returns the *calling captain's own* driver, assigned request(s), route metrics, route sequences, and optimizer recommendation. Anonymous/public requests (no bearer token) fall back to the shared demo driver, matching the original single-captain demo flow.
- `POST /captain/recommendations/respond`
  - Records an accept or reject decision. Accept decisions go through optimistic-locking (`app/services/concurrency.py`); a request already claimed by another captain returns `409 Conflict` instead of silently overwriting it.
- `POST /captain/recommendations/complete`
  - Closes out the calling captain's active route and returns them to the pool.

### Dashboard

- `GET /dashboard`
  - Returns high-level metrics, recent activity, live assignment-engine stats (candidates evaluated/pruned, solve time, optimal-vs-greedy comparison), and concurrency-guard stats (conflicts prevented, last stress-test result).

### Demo

- `GET /demo/load`
  - Seeds the single demo ride, parcel, and captain scenario.
- `POST /demo/seed-fleet`
  - Creates several real captain accounts (not fake rows — full `User` + `Driver` records you can log into) plus scattered ride/parcel requests, so the assignment engine has an actual multi-driver pool to solve over.
- `POST /demo/stress/concurrency`
  - Fires several simultaneous accept attempts at the same ride+parcel pair through the real accept code path, to demonstrate the concurrency guard on demand.

## System Design

RouteFusion's captain matching is a real assignment-problem pipeline, not a per-driver heuristic score. The full implementation lives in `backend/app/services/`.

### The problem

Matching drivers to rides and parcels is a **3-dimensional assignment problem** (driver × ride × parcel), which is NP-hard in general. Rather than brute-forcing it, RouteFusion decomposes it into two sequential **2-dimensional assignment problems**, each solved optimally:

- **Stage 1 — drivers × open rides.** Cost = haversine distance from a driver's current location to each ride's pickup. Solved with a from-scratch Kuhn-Munkres (Hungarian) implementation (`hungarian.py`), O(n³) on the reduced candidate matrix.
- **Stage 2 — (driver, assigned ride) × open parcels.** Cost = the cheapest extra distance of bundling that parcel onto the driver's already-assigned ride, minimized over all 6 valid stop orderings that respect each job's own pickup-before-drop constraint (`route_optimizer.enumerate_valid_orderings` / `best_combined_extra_distance`). Solved with the same Hungarian function.

This decomposition is optimal *within* each stage but not guaranteed globally optimal across both stages — an explicit, documented trade-off in exchange for tractability. It also means Hungarian's augmenting-path search can match **more drivers** than a naive greedy pass would (greedy never revisits an earlier choice that turns out to block a later match), which is why the dashboard's "optimal vs greedy" comparison only claims a distance improvement when both matched the same number of pairs — otherwise it reports the actual win: more drivers matched.

### Pruning

Before either stage builds its cost matrix, candidates are pruned with a uniform spatial grid (`spatial_grid.py`) — the same bucketing principle behind geohash/H3, simplified to a fixed-size grid with a 3×3 neighbor-cell lookup. This keeps the cost matrix small at scale. If a cell's local neighborhood is empty, pruning falls back to the full candidate set for that driver/ride rather than reporting no match — pruning is only ever a performance optimization, never a correctness risk.

### Concurrency

Two captains can be shown overlapping recommendations and both try to accept at once. `services/concurrency.py` claims a ride/parcel with a conditional `UPDATE ... WHERE status='open' AND version=<snapshot>` — an optimistic-locking pattern that only needs an atomic conditional update, not `SELECT ... FOR UPDATE`, so it works identically on the app's default transient SQLite store and on Postgres. Zero rows affected means someone else claimed it first; the caller gets a `409` instead of silently double-booking the request. The `/demo/stress/concurrency` endpoint proves this on demand by firing N simultaneous accept attempts at the same pair through this exact code path.

One caveat specific to the default transient mode: it backs every request with a single shared in-memory SQLite connection (`StaticPool`), and the `sqlite3` driver isn't safe for truly concurrent access from multiple threads at once. The stress-test endpoint serializes the DB round-trip of each simulated attempt through a lock for that reason (`SQLITE_SINGLE_WRITER_LOCK`) — the optimistic-locking version check is still what decides the one winner; the lock only protects the driver itself from corrupting a shared connection. Real concurrent Postgres connections wouldn't need it.

## UI Wireframes

The visual wireframes live in [docs/ui-wireframes.md](docs/ui-wireframes.md). They outline the startup-style layout, navigation, form pages, captain view, live map, and dashboard composition before implementation.

The component tree and persistent split-layout architecture live in [docs/architecture.md](docs/architecture.md). Deployment notes live in [docs/deployment-guide.md](docs/deployment-guide.md).

## Assumptions

- Google Maps support is implemented with a graceful fallback visualization when no browser API key is present locally.
- Transient in-memory mode is the default so the demo stays fast and starts clean on every fresh boot.
- PostgreSQL is optional and should only be enabled when you explicitly want persistent storage.
- Demo mode is the default happy path and is preloaded with VIT Vellore, CMC Hospital, Katpadi Railway Station, and Gandhi Nagar sample data.

## Local Run

### Backend

```bash
cd routeFusion
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
```

For backend verification helpers, install the dev extras:

```bash
.venv/bin/pip install -r backend/dev-requirements.txt
```

### Frontend

```bash
cd routeFusion/frontend
npm install
npm run dev
```

Optional browser environment variables:

- `VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000`
- `VITE_GOOGLE_MAPS_API_KEY` enables the live Google Maps renderer instead of the built-in fallback map. The Google Cloud key should have `Maps JavaScript API`, `Places API`, and `Directions API` enabled for road-snapped routes.

## Security Note

- Keep `.env` out of version control.
- Rotate any database password or API keys before making the repo public or handing it off.
- If you re-enable PostgreSQL, prefer Supabase's pooler connection and URL-encode special characters in the password.
