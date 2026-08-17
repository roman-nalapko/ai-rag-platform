import httpx
import pytest


@pytest.mark.asyncio
async def test_demo_ui_is_served(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/demo/")

    assert response.status_code == 200
    assert "AI RAG Platform" in response.text
