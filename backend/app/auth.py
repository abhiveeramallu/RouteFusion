from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Driver, RefreshToken, TokenBlacklist, User
from app.services.locations import resolve_location

DEMO_EMAIL = "demo@routefusion.app"
DEMO_PASSWORD = "routefusion-demo"
DEMO_NAME = "RouteFusion Demo Operator"
SUPPORTED_SIGNUP_ROLES = {"rider", "captain", "operator"}
password_hasher = PasswordHasher()


TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def legacy_hash_password(password: str) -> str:
    settings = get_settings()
    return hashlib.sha256(f"{settings.jwt_secret}:{password}".encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except InvalidHashError:
        return hmac.compare_digest(legacy_hash_password(plain_password), hashed_password)
    except VerifyMismatchError:
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(hashed_password)
    except InvalidHashError:
        return True


def hash_token_value(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_expiry_from_payload(payload: dict[str, Any]) -> datetime:
    raw_exp = payload.get("exp")
    if isinstance(raw_exp, datetime):
        return to_naive_utc(raw_exp)
    if isinstance(raw_exp, (int, float)):
        return datetime.fromtimestamp(raw_exp, UTC).replace(tzinfo=None)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token expiry.")


def create_token(subject: str, role: str, token_type: TokenType, is_demo: bool) -> tuple[str, str]:
    settings = get_settings()
    expires_at = utcnow() + (
        timedelta(minutes=settings.jwt_access_exp_minutes)
        if token_type == "access"
        else timedelta(days=settings.jwt_refresh_exp_days)
    )
    jti = uuid.uuid4().hex
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "jti": jti,
        "is_demo": is_demo,
        "iat": utcnow(),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), jti


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc

    token_type = payload.get("type")
    if expected_type and token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Expected a {expected_type} token.",
        )

    if not payload.get("sub") or not payload.get("jti"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incomplete authentication token.",
        )

    return payload


def get_demo_user(db: Session, email: str = DEMO_EMAIL) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def ensure_captain_profile(db: Session, user: User) -> Driver:
    if user.driver:
        return user.driver

    base_location = resolve_location("VIT Vellore")
    driver = Driver(
        user_id=user.id,
        display_name=user.full_name,
        vehicle_type="Hybrid Cab",
        status="available",
        current_lat=base_location.lat,
        current_lng=base_location.lng,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


def ensure_demo_user(db: Session) -> User:
    user = get_demo_user(db)
    if user:
        if not user.is_demo or user.role != "operator" or password_needs_rehash(user.hashed_password):
            user.is_demo = True
            user.role = "operator"
            user.hashed_password = hash_password(DEMO_PASSWORD)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    user = User(
        email=normalize_email(DEMO_EMAIL),
        full_name=DEMO_NAME,
        hashed_password=hash_password(DEMO_PASSWORD),
        role="operator",
        is_demo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_demo_user(db: Session) -> User:
    user = ensure_demo_user(db)
    if not verify_password(DEMO_PASSWORD, user.hashed_password):
        user.hashed_password = hash_password(DEMO_PASSWORD)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None

    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
        db.add(user)
        db.commit()
        db.refresh(user)

    if user.role == "captain" and not user.driver:
        ensure_captain_profile(db, user)
        db.refresh(user)

    return user


def register_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    role: str,
) -> User:
    if role not in SUPPORTED_SIGNUP_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported signup role.")

    normalized_email = normalize_email(email)
    if get_user_by_email(db, normalized_email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account already exists for this email.")

    user = User(
        email=normalized_email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        role=role,
        is_demo=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if role == "captain":
        ensure_captain_profile(db, user)
        db.refresh(user)

    return user


def blacklist_token(
    db: Session,
    *,
    user_id: int | None,
    jti: str,
    token_type: str,
    expires_at: datetime,
) -> None:
    existing = db.scalar(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
    if existing:
        return
    db.add(
        TokenBlacklist(
            user_id=user_id,
            jti=jti,
            token_type=token_type,
            expires_at=to_naive_utc(expires_at),
        )
    )


def is_token_blacklisted(db: Session, jti: str | None) -> bool:
    if not jti:
        return True
    return db.scalar(select(TokenBlacklist).where(TokenBlacklist.jti == jti)) is not None


def issue_session_tokens(db: Session, user: User) -> SessionTokens:
    access_token, _access_jti = create_token(str(user.id), user.role, "access", user.is_demo)
    refresh_token, refresh_jti = create_token(str(user.id), user.role, "refresh", user.is_demo)
    refresh_payload = decode_token(refresh_token, expected_type="refresh")
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=refresh_jti,
            token_hash=hash_token_value(refresh_token),
            expires_at=token_expiry_from_payload(refresh_payload),
        )
    )
    db.commit()
    return SessionTokens(access_token=access_token, refresh_token=refresh_token)


def refresh_user_session(db: Session, refresh_token: str) -> tuple[User, SessionTokens]:
    payload = decode_token(refresh_token, expected_type="refresh")
    user_id = int(payload["sub"])
    jti = str(payload["jti"])

    if is_token_blacklisted(db, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked.")

    record = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti, RefreshToken.user_id == user_id))
    if not record or record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is no longer active.")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired.")
    if not hmac.compare_digest(record.token_hash, hash_token_value(refresh_token)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch.")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    record.revoked_at = datetime.utcnow()
    blacklist_token(
        db,
        user_id=user.id,
        jti=jti,
        token_type="refresh",
        expires_at=token_expiry_from_payload(payload),
    )
    db.add(record)

    access_token, _access_jti = create_token(str(user.id), user.role, "access", user.is_demo)
    next_refresh_token, next_refresh_jti = create_token(str(user.id), user.role, "refresh", user.is_demo)
    next_refresh_payload = decode_token(next_refresh_token, expected_type="refresh")
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=next_refresh_jti,
            token_hash=hash_token_value(next_refresh_token),
            expires_at=token_expiry_from_payload(next_refresh_payload),
        )
    )
    db.commit()

    return user, SessionTokens(access_token=access_token, refresh_token=next_refresh_token)


def logout_user(
    db: Session,
    *,
    user: User,
    access_payload: dict[str, Any],
    refresh_token: str | None = None,
) -> None:
    blacklist_token(
        db,
        user_id=user.id,
        jti=str(access_payload["jti"]),
        token_type="access",
        expires_at=token_expiry_from_payload(access_payload),
    )

    if refresh_token:
        payload = decode_token(refresh_token, expected_type="refresh")
        if int(payload["sub"]) != user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token does not belong to the current user.",
            )

        record = db.scalar(select(RefreshToken).where(RefreshToken.jti == str(payload["jti"])))
        if record and record.revoked_at is None:
            record.revoked_at = datetime.utcnow()
            db.add(record)
        blacklist_token(
            db,
            user_id=user.id,
            jti=str(payload["jti"]),
            token_type="refresh",
            expires_at=token_expiry_from_payload(payload),
        )
    else:
        active_refresh_tokens = list(
            db.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        )
        for record in active_refresh_tokens:
            record.revoked_at = datetime.utcnow()
            db.add(record)
            blacklist_token(
                db,
                user_id=user.id,
                jti=record.jti,
                token_type="refresh",
                expires_at=record.expires_at,
            )

    db.commit()
