from collections.abc import AsyncIterator

import httpx
import pytest_asyncio

from app.db.session import get_db
from app.main import app


async def override_get_db() -> AsyncIterator[object]:
    """Provide a sentinel session; validation tests must never use it."""

    yield object()


@pytest_asyncio.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides = original_overrides
