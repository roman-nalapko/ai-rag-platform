import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)
from app.db.session import get_db
from app.main import app


async def override_get_db() -> AsyncIterator[object]:
    yield object()


def test_access_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1)

    token, expires_in = create_access_token(user_id)

    assert expires_in == 60
    assert decode_access_token(token) == user_id


def test_access_token_expires_at_exact_expiration_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 0)
    monkeypatch.setattr("app.core.security.time.time", lambda: 1_000.0)

    token, _ = create_access_token(uuid.uuid4())

    with pytest.raises(InvalidTokenError, match="expired"):
        decode_access_token(token)


@pytest.mark.asyncio
async def test_protected_endpoint_requires_bearer_token() -> None:
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/search",
                json={
                    "knowledge_base_id": str(uuid.uuid4()),
                    "query": "dependencies",
                },
            )
    finally:
        app.dependency_overrides = original_overrides

    assert response.status_code == 401
    assert response.json() == {"detail": "Bearer token required"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/users", {"email": "disabled@example.com"}),
        ("POST", "/auth/demo-token", {"user_id": str(uuid.uuid4())}),
    ],
)
async def test_demo_endpoints_are_hidden_when_demo_mode_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    payload: dict[str, str],
) -> None:
    monkeypatch.setattr(settings, "DEMO_MODE_ENABLED", False)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.request(method, path, json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}
