from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ["DATABASE_URL"] = "sqlite:///./routefusion-test-runtime.db"

from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.routes import demo as demo_routes


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Route handlers that open their own sessions directly (rather than via
    # Depends(get_db)) — currently only the concurrency stress test's worker
    # threads, which need real thread-local sessions of their own — import
    # SessionLocal by name, so overriding app.database.SessionLocal alone
    # wouldn't reach them. Patch the name where it's actually used so those
    # code paths hit this test's isolated database too, instead of silently
    # falling through to the real app.database engine.
    monkeypatch.setattr(demo_routes, "SessionLocal", testing_session_local)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
