import httpx
import pytest


@pytest.mark.asyncio
async def test_health_endpoint(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "running",
        "mode": "local-ai",
    }
