# RouteFusion Deployment Guide

## Local Development

### Backend

```bash
cd routeFusion
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd routeFusion/frontend
npm install
npm run dev
```

## Required Environment Variables

### Frontend

- `VITE_API_BASE_URL`
- `VITE_GOOGLE_MAPS_API_KEY`

### Backend

- `DATABASE_URL`
- `JWT_SECRET`
- `CORS_ORIGINS`

## Production Topology

### Frontend

- Vite build output served by Vercel, Netlify, or static hosting

### Backend

- FastAPI app served by Uvicorn or Gunicorn/Uvicorn workers
- PostgreSQL database for persisted rides, parcels, and route decisions

## Recommended Production Checklist

1. Set `DATABASE_URL` to PostgreSQL
2. Replace demo JWT secret with a strong secret
3. Set CORS to the production frontend domain
4. Add `VITE_GOOGLE_MAPS_API_KEY` with Maps JavaScript API + Directions enabled
5. Verify `/health`, `/demo/load`, `/captain/recommendations`, and `/dashboard`
6. Build frontend with `npm run build`
7. Run backend smoke tests before deploy
