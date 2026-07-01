# RouteFusion

RouteFusion is a demo-first MVP that shows how a captain can combine a passenger ride and a parcel delivery into one optimized trip. The latest UI direction uses an Uber-inspired persistent map layout with a shared left-side booking hub for ride requests, parcel requests, and captain decisions.

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
- Recommendation logic favors explainability over overly complex optimization.
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

The canonical SQL schema lives in [backend/schema.sql](/Users/vabhiram/Documents/routeFusion/backend/schema.sql). The core tables are:

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
  - Returns the latest driver, nearby requests, route metrics, route sequences, and optimizer recommendation.
- `POST /captain/recommendations/respond`
  - Records an accept or reject decision for the recommended combined trip.

### Dashboard

- `GET /dashboard`
  - Returns high-level metrics and recent activity.

### Demo

- `GET /demo/load`
  - Seeds the demo ride, parcel, and captain records and returns the initialized scenario.

## UI Wireframes

The visual wireframes live in [docs/ui-wireframes.md](/Users/vabhiram/Documents/routeFusion/docs/ui-wireframes.md). They outline the startup-style layout, navigation, form pages, captain view, live map, and dashboard composition before implementation.

The component tree and persistent split-layout architecture live in [docs/architecture.md](/Users/vabhiram/Documents/routeFusion/docs/architecture.md). Deployment notes live in [docs/deployment-guide.md](/Users/vabhiram/Documents/routeFusion/docs/deployment-guide.md).

## Assumptions

- Google Maps support is implemented with a graceful fallback visualization when no browser API key is present locally.
- PostgreSQL is the target deployment database, but SQLite is allowed locally so the demo can run without standing up infrastructure first.
- Demo mode is the default happy path and is preloaded with VIT Vellore, CMC Hospital, Katpadi Railway Station, and Gandhi Nagar sample data.

## Local Run

### Backend

```bash
cd /Users/vabhiram/Documents/routeFusion
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
cd /Users/vabhiram/Documents/routeFusion/frontend
npm install
npm run dev
```

Optional browser environment variables:

- `VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000`
- `VITE_GOOGLE_MAPS_API_KEY` enables the live Google Maps renderer instead of the built-in fallback map. The Google Cloud key should have `Maps JavaScript API`, `Places API`, and `Directions API` enabled for road-snapped routes.
