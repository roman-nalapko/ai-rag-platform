import uuid

import httpx
import pytest

VALID_UUID = str(uuid.UUID("11111111-1111-4111-8111-111111111111"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "not-an-email"},
        {"email": "engineer@example.com", "is_admin": True},
    ],
)
async def test_user_creation_rejects_invalid_payloads(
    api_client: httpx.AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await api_client.post("/users", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"user_id": "not-a-uuid", "name": "Engineering"},
        {"user_id": VALID_UUID, "name": "   "},
        {"user_id": VALID_UUID, "name": "Engineering", "unknown": "field"},
    ],
)
async def test_knowledge_base_creation_rejects_invalid_payloads(
    api_client: httpx.AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await api_client.post("/knowledge-bases", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"query": "dependencies"},
        {"knowledge_base_id": VALID_UUID, "query": "   "},
        {"knowledge_base_id": VALID_UUID, "query": "dependencies", "limit": 0},
        {"knowledge_base_id": VALID_UUID, "query": "dependencies", "limit": 51},
    ],
)
async def test_search_rejects_invalid_requests(
    api_client: httpx.AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await api_client.post("/search", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"question": "What is indexed?"},
        {"knowledge_base_id": VALID_UUID, "question": "   "},
        {"knowledge_base_id": VALID_UUID, "question": "What?", "limit": 0},
        {"knowledge_base_id": VALID_UUID, "question": "What?", "limit": 11},
        {
            "knowledge_base_id": VALID_UUID,
            "conversation_id": "not-a-uuid",
            "question": "What?",
        },
    ],
)
async def test_qa_rejects_invalid_requests(
    api_client: httpx.AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await api_client.post("/qa/ask", json=payload)

    assert response.status_code == 422
