from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_demo_mode
from app.db.session import get_db
from app.schemas.auth import (
    DemoTokenRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth import (
    AuthEmailAlreadyExistsError,
    AuthInvalidCredentialsError,
    AuthService,
    AuthUserNotFoundError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description=(
        "Create a new user with **email + password** and receive a JWT. "
        "Use this instead of the demo-token flow for persistent accounts."
    ),
)
async def register(
    request: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    try:
        token = await AuthService(session).register(request.email, request.password)
    except AuthEmailAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return TokenResponse(access_token=token.value, expires_in=token.expires_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    request: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    try:
        token = await AuthService(session).login(request.email, request.password)
    except AuthInvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    return TokenResponse(access_token=token.value, expires_in=token.expires_in)


# ── Demo-mode-only endpoint (kept for backward-compatibility) ─────────────────

_demo_router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    dependencies=[Depends(require_demo_mode)],
)


@_demo_router.post(
    "/demo-token",
    response_model=TokenResponse,
    summary="Issue a demo token (demo mode only)",
    description=(
        "Returns a JWT for an **existing** user by ID. "
        "Only available when `DEMO_MODE_ENABLED=true`. "
        "For production use, prefer `/auth/register` and `/auth/login`."
    ),
)
async def create_demo_token(
    request: DemoTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    try:
        token = await AuthService(session).create_demo_token(request.user_id)
    except AuthUserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return TokenResponse(access_token=token.value, expires_in=token.expires_in)
