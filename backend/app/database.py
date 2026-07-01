from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


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


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
