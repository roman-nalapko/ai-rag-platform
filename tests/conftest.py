import os
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import cast
from uuid import UUID

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/rag",
)
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("LM_STUDIO_CHAT_MODEL", "test-chat-model")
os.environ.setdefault("LM_STUDIO_EMBEDDING_MODEL", "test-embedding-model")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-local-testing")

import httpx
import pytest_asyncio

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import User

TEST_USER_ID = UUID("11111111-1111-4111-8111-111111111111")


async def override_get_db() -> AsyncIterator[object]:
    """Provide a sentinel session; validation tests must never use it."""

    yield object()


async def override_get_current_user() -> User:
    return cast(
        User,
        SimpleNamespace(
            id=TEST_USER_ID,
            email="engineer@example.com",
        ),
    )


@pytest_asyncio.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides = original_overrides
