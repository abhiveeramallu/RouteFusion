from __future__ import annotations

import threading
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_kwargs = {
    "connect_args": connect_args,
}
if not settings.database_url.startswith("sqlite"):
    # Keep pooled Postgres connections healthy on hosted platforms like
    # Render + Supabase where idle sockets can go stale between bursts.
    engine_kwargs.update(
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=3,
        max_overflow=5,
    )
elif settings.transient_mode:
    # A single shared in-memory connection keeps transient demo state fast
    # while still allowing normal SQLAlchemy sessions per request.
    engine_kwargs.update(
        poolclass=StaticPool,
    )

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

# sqlite3 connections (even file-based ones opened with check_same_thread=
# False, and especially the single shared StaticPool connection used in
# transient mode) aren't safe for genuinely concurrent access from multiple
# threads at once — unlike Postgres, which handles real concurrent
# connections natively. FastAPI dispatches sync `def` route handlers via a
# thread pool, so two real concurrent HTTP requests already run on separate
# threads today; without this, they can corrupt each other's queries against
# the same physical sqlite connection. This lives at the session layer
# (get_db, below) rather than as a lock sprinkled into individual routes, so
# every request is protected by construction instead of by a caller
# remembering to opt in.
SQLITE_SINGLE_WRITER_LOCK = threading.Lock()
_SERIALIZE_SQLITE_SESSIONS = settings.database_url.startswith("sqlite")


def synchronize_legacy_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        inspector = inspect(connection)

        if inspector.has_table("users"):
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "is_demo" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0"))

        if inspector.has_table("rides"):
            ride_columns = {column["name"] for column in inspector.get_columns("rides")}
            if "created_by_user_id" not in ride_columns:
                connection.execute(text("ALTER TABLE rides ADD COLUMN created_by_user_id INTEGER"))

        if inspector.has_table("parcels"):
            parcel_columns = {column["name"] for column in inspector.get_columns("parcels")}
            if "created_by_user_id" not in parcel_columns:
                connection.execute(text("ALTER TABLE parcels ADD COLUMN created_by_user_id INTEGER"))

        if inspector.has_table("rides"):
            ride_columns = {column["name"] for column in inspector.get_columns("rides")}
            if "version" not in ride_columns:
                connection.execute(text("ALTER TABLE rides ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))
            if "assigned_driver_id" not in ride_columns:
                connection.execute(text("ALTER TABLE rides ADD COLUMN assigned_driver_id INTEGER"))

        if inspector.has_table("parcels"):
            parcel_columns = {column["name"] for column in inspector.get_columns("parcels")}
            if "version" not in parcel_columns:
                connection.execute(text("ALTER TABLE parcels ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))
            if "assigned_driver_id" not in parcel_columns:
                connection.execute(text("ALTER TABLE parcels ADD COLUMN assigned_driver_id INTEGER"))


def get_db() -> Generator[Session, None, None]:
    if _SERIALIZE_SQLITE_SESSIONS:
        with SQLITE_SINGLE_WRITER_LOCK:
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
