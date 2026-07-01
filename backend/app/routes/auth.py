from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    authenticate_demo_user,
    authenticate_user,
    issue_session_tokens,
    logout_user,
    refresh_user_session,
    register_user,
)
from app.database import get_db
from app.dependencies import get_access_token_payload, get_current_user
from app.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from app.services.demo_seed import ensure_demo_driver, seed_demo_scenario

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = register_user(
        db,
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
    )
    tokens = issue_session_tokens(db, user)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    tokens = issue_session_tokens(db, user)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_session(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user, tokens = refresh_user_session(db, payload.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: LogoutRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    access_payload=Depends(get_access_token_payload),
) -> MessageResponse:
    logout_user(
        db,
        user=current_user,
        access_payload=access_payload,
        refresh_token=payload.refresh_token,
    )
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserRead)
def get_me(current_user=Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/demo-login", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_demo_user(db)
    ensure_demo_driver(db)
    seed_demo_scenario(db)
    tokens = issue_session_tokens(db, user)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserRead.model_validate(user),
    )
