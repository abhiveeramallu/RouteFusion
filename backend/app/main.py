from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.auth import ensure_demo_user
from app.config import get_settings
from app.database import Base, SessionLocal, engine, synchronize_legacy_schema
from app.routes.auth import router as auth_router
from app.routes.captain import router as captain_router
from app.routes.dashboard import router as dashboard_router
from app.routes.demo import router as demo_router
from app.routes.parcel import router as parcel_router
from app.routes.ride import router as ride_router
from app.services.demo_seed import ensure_demo_driver


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        synchronize_legacy_schema()
    elif not inspect(engine).has_table("users"):
        raise RuntimeError("Database schema is missing. Run `alembic upgrade head` before starting RouteFusion.")

    db = SessionLocal()
    try:
        ensure_demo_user(db)
        ensure_demo_driver(db)
    finally:
        db.close()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(ride_router)
app.include_router(parcel_router)
app.include_router(captain_router)
app.include_router(dashboard_router)
app.include_router(demo_router)
