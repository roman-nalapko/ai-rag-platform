"""Tests for the new /auth/register and /auth/login endpoints."""

import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.api.dependencies import get_current_user, get_db
from app.core.security import InvalidPasswordError, hash_password, verify_password
from app.main import app
from app.models.user import User

# ── Password hashing unit tests ────────────────────────────────────────────────

def test_hash_password_produces_bcrypt_hash() -> None:
    hashed = hash_password("MySecretPassword")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_verify_password_correct() -> None:
    plain = "correcthorsebatterystaple"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_invalid_hash() -> None:
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_hash_password_too_short() -> None:
    with pytest.raises(InvalidPasswordError, match="8 characters"):
        hash_password("short")


# ── /auth/register endpoint ────────────────────────────────────────────────────

def _make_user(user_id: uuid.UUID, email: str) -> User:
    from types import SimpleNamespace
    return SimpleNamespace(id=user_id, email=email, hashed_password=None)  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_token() -> None:
    """POST /auth/register should create a user and return a bearer token."""
    created_user_id = uuid.uuid4()

    mock_session = MagicMock()

    async def _add(obj: Any) -> None:
        obj.id = created_user_id

    mock_session.add = MagicMock(side_effect=_add)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", created_user_id))
    mock_session.execute = AsyncMock()

    async def override_db() -> AsyncIterator[Any]:
        yield mock_session

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides.pop(get_current_user, None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/auth/register",
                json={"email": "new@example.com", "password": "strongpassword"},
            )
    finally:
        app.dependency_overrides = original

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_register_requires_password_min_length() -> None:
    """Pydantic should reject passwords shorter than 8 characters."""
    original = app.dependency_overrides.copy()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/auth/register",
                json={"email": "x@x.com", "password": "short"},
            )
    finally:
        app.dependency_overrides = original

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_requires_valid_email() -> None:
    original = app.dependency_overrides.copy()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/auth/register",
                json={"email": "not-an-email", "password": "strongpassword"},
            )
    finally:
        app.dependency_overrides = original

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401() -> None:
    """POST /auth/login with bad credentials must return 401, not 500."""
    mock_session = MagicMock()

    # Simulate user found with a different password hash
    stored_hash = hash_password("correct-password")
    fake_user = MagicMock()
    fake_user.id = uuid.uuid4()
    fake_user.email = "user@example.com"
    fake_user.hashed_password = stored_hash

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_db() -> AsyncIterator[Any]:
        yield mock_session

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides.pop(get_current_user, None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "wrong-password"},
            )
    finally:
        app.dependency_overrides = original

    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_with_nonexistent_user_returns_401() -> None:
    """Login with unknown email must return 401 (no email enumeration)."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_db() -> AsyncIterator[Any]:
        yield mock_session

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides.pop(get_current_user, None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/auth/login",
                json={"email": "ghost@example.com", "password": "doesnotmatter"},
            )
    finally:
        app.dependency_overrides = original

    assert response.status_code == 401
