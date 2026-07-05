import uuid

import httpx
import pytest


@pytest.mark.asyncio
async def test_request_id_header_is_valid_and_unique(
    api_client: httpx.AsyncClient,
) -> None:
    first_response = await api_client.get("/health")
    second_response = await api_client.get("/health")

    first_request_id = first_response.headers["x-request-id"]
    second_request_id = second_response.headers["x-request-id"]

    assert uuid.UUID(first_request_id).version == 4
    assert uuid.UUID(second_request_id).version == 4
    assert first_request_id != second_request_id
