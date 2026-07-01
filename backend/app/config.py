from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def _load_local_env_files() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[2]

    for env_path in (repo_root / ".env", backend_dir / ".env"):
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            cleaned_key = key.strip()
            cleaned_value = value.strip().strip('"').strip("'")
            os.environ.setdefault(cleaned_key, cleaned_value)


def _default_database_url() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    sqlite_path = repo_root / "routefusion.db"
    return f"sqlite:///{sqlite_path}"


def _transient_database_url() -> str:
    return "sqlite:///:memory:"


_load_local_env_files()


@dataclass(frozen=True)
class Settings:
    app_name: str
    transient_mode: bool
    database_url: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_access_exp_minutes: int
    jwt_refresh_exp_days: int
    cors_origins: list[str]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    transient_mode = _env_flag("ROUTEFUSION_TRANSIENT_MODE", False)
    return Settings(
        app_name="RouteFusion",
        transient_mode=transient_mode,
        database_url=(
            _transient_database_url()
            if transient_mode
            else os.getenv(
                "DATABASE_URL",
                _default_database_url(),
            )
        ),
        jwt_secret=os.getenv("JWT_SECRET", "routefusion-demo-secret"),
        jwt_algorithm="HS256",
        jwt_access_exp_minutes=int(
            os.getenv("JWT_ACCESS_EXP_MINUTES", os.getenv("JWT_EXP_MINUTES", "30"))
        ),
        jwt_refresh_exp_days=int(os.getenv("JWT_REFRESH_EXP_DAYS", "14")),
        cors_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
    )
