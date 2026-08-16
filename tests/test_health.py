import httpx
import pytest

from app.db.session import get_db
from app.main import app
from app.rag.vector_store import VectorStoreError, get_vector_store


@pytest.mark.asyncio
async def test_health_endpoint(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "running",
        "mode": "local-ai",
    }


class FakeReadySession:
    async def execute(self, _: object) -> None:
        return None


class FakeReadyVectorStore:
    async def ping(self) -> None:
        return None


class FakeFailingVectorStore:
    async def ping(self) -> None:
        raise VectorStoreError("qdrant unavailable")


async def override_ready_db() -> object:
    yield FakeReadySession()


def override_ready_vector_store() -> FakeReadyVectorStore:
    return FakeReadyVectorStore()


def override_failing_vector_store() -> FakeFailingVectorStore:
    return FakeFailingVectorStore()


@pytest.mark.asyncio
async def test_readiness_endpoint_reports_ready(
    api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_db] = override_ready_db
    app.dependency_overrides[get_vector_store] = override_ready_vector_store

    response = await api_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": "ok",
            "qdrant": "ok",
        },
    }


@pytest.mark.asyncio
async def test_readiness_endpoint_returns_503_when_qdrant_fails(
    api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_db] = override_ready_db
    app.dependency_overrides[get_vector_store] = override_failing_vector_store

    response = await api_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Qdrant is unavailable"}
