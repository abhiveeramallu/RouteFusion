# RouteFusion Architecture

## Product Direction

RouteFusion is a ride-plus-parcel optimization platform presented through an Uber-inspired web experience:

- Persistent top navigation
- Persistent map canvas on desktop
- Left-side task panel that changes by route
- Fast booking flow for rides, parcels, and combined previews
- Premium captain recommendation experience

The goal is not to clone Uber, but to borrow the clarity of its split-panel map-first layout while telling a different operational story.

## Experience Layout

### Desktop

- Top navigation spans the full width
- Main workspace uses a `30% / 70%` split
- Left side is the active panel for forms, dashboard, or captain workflow
- Right side is a persistent live map

### Mobile

- Top navigation collapses into a horizontal scroller
- Map stays visible near the top
- Active panel content stacks below the map

## Component Tree

```text
App
└── AppShell
    ├── TopNav
    ├── StatusRail
    └── Workspace
        ├── SidePanelFrame
        │   ├── PanelHeader
        │   ├── RoutePanelSwitch
        │   │   ├── HomePanel
        │   │   ├── ParcelPanel
        │   │   ├── RidePanel
        │   │   ├── CaptainPanel
        │   │   ├── LiveMapPanel
        │   │   ├── DashboardPanel
        │   │   └── ProfilePanel
        │   └── PanelFooter
        └── MapStage
            ├── LiveMapCanvas
            ├── MapLegend
            ├── RouteSummaryDock
            └── FloatingCaptainBadge
```

## Frontend Structure

```text
frontend/src/
├── components/
│   ├── AppShell.tsx
│   ├── DockStat.tsx
│   ├── LiveMapCanvas.tsx
│   ├── MapLegend.tsx
│   ├── PanelCard.tsx
│   ├── PanelHeader.tsx
│   ├── TopNav.tsx
│   └── ui/
├── context/
│   └── RouteFusionContext.tsx
├── lib/
│   ├── api.ts
│   ├── constants.ts
│   ├── format.ts
│   ├── mapScenario.ts
│   └── routeOptimizer.ts
├── pages/
│   ├── CaptainCornerPage.tsx
│   ├── DashboardPage.tsx
│   ├── HomePage.tsx
│   ├── LiveMapPage.tsx
│   ├── ParcelRequestPage.tsx
│   ├── ProfilePage.tsx
│   └── RideRequestPage.tsx
├── App.tsx
├── index.css
├── main.tsx
└── types.ts
```

## Data Flow

1. Frontend boots through demo JWT login.
2. Demo data is loaded automatically on first render.
3. RouteFusion context stores:
   - dashboard metrics
   - current recommendation
   - rides and parcels
   - device geolocation if available
   - form-driven preview state
4. Panel route determines the left-side content.
5. Map scenario is derived from:
   - current route
   - preview inputs
   - backend recommendation
   - current captain location
6. Google Maps renders live markers and route overlays when an API key is present.
7. A fallback canvas renders the same routing story when a key is absent.

## Mapping Strategy

### With Google Maps API Key

- Load Maps JavaScript API through `@react-google-maps/api`
- Resolve directions with `google.maps.DirectionsService`
- Render:
  - passenger route in green
  - parcel route in blue
  - optimized route in purple
- Animate optimized route reveal
- Animate captain marker along the optimized path
- Attempt browser geolocation for live captain positioning

### Without Google Maps API Key

- Render a branded vector route board
- Preserve route colors, markers, and sequencing
- Keep the demo functional during local development

## Backend Responsibilities

- Issue demo JWT auth token
- Persist rides, parcels, and route decisions
- Seed the VIT -> CMC and Katpadi -> Gandhi Nagar demo scenario
- Compute authoritative optimization recommendations
- Aggregate dashboard analytics

## Optimization Split

### Backend

- Source of truth for captain recommendation
- Produces accepted/rejected route decisions

### Frontend

- Uses `routeOptimizer.ts` for instant map preview and home-panel estimates
- Mirrors the backend scoring style for responsive UX

## Deployment Notes

- Frontend can deploy to Vercel or Netlify
- Backend can deploy to Render, Fly.io, or a Dockerized VM
- PostgreSQL is the target production database
- SQLite remains acceptable for local demo development
