import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.api import conversations as conversations_api
from app.services.conversation import ConversationKnowledgeBaseNotFoundError

CONVERSATION_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
KNOWLEDGE_BASE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def conversation_stub() -> SimpleNamespace:
    return SimpleNamespace(
        id=CONVERSATION_ID,
        knowledge_base_id=KNOWLEDGE_BASE_ID,
        title="Test Conversation",
        created_at=datetime(2026, 8, 17, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_list_conversations_returns_200(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_args: dict[str, Any] = {}

    class FakeConversationService:
        def __init__(self, _: object) -> None:
            pass

        async def list_for_knowledge_base(
            self,
            knowledge_base_id: uuid.UUID,
            current_user_id: uuid.UUID,
            limit: int,
            offset: int,
        ) -> list[Any]:
            captured_args["knowledge_base_id"] = knowledge_base_id
            captured_args["current_user_id"] = current_user_id
            captured_args["limit"] = limit
            captured_args["offset"] = offset
            return [conversation_stub()]

    monkeypatch.setattr(
        conversations_api,
        "ConversationService",
        FakeConversationService,
    )

    response = await api_client.get(
        f"/conversations?knowledge_base_id={KNOWLEDGE_BASE_ID}&limit=10&offset=5"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(CONVERSATION_ID)
    assert data[0]["title"] == "Test Conversation"
    assert captured_args["knowledge_base_id"] == KNOWLEDGE_BASE_ID
    assert captured_args["limit"] == 10
    assert captured_args["offset"] == 5


@pytest.mark.asyncio
async def test_list_conversations_returns_404_when_knowledge_base_not_found(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConversationService:
        def __init__(self, _: object) -> None:
            pass

        async def list_for_knowledge_base(
            self,
            knowledge_base_id: uuid.UUID,
            current_user_id: uuid.UUID,
            limit: int,
            offset: int,
        ) -> list[Any]:
            raise ConversationKnowledgeBaseNotFoundError("Knowledge base not found")

    monkeypatch.setattr(
        conversations_api,
        "ConversationService",
        FakeConversationService,
    )

    response = await api_client.get(
        f"/conversations?knowledge_base_id={KNOWLEDGE_BASE_ID}"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Knowledge base not found"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "",
        "limit=10",
        f"knowledge_base_id={KNOWLEDGE_BASE_ID}&limit=0",
        f"knowledge_base_id={KNOWLEDGE_BASE_ID}&limit=101",
        f"knowledge_base_id={KNOWLEDGE_BASE_ID}&offset=-1",
    ],
)
async def test_list_conversations_validates_query_params(
    api_client: httpx.AsyncClient,
    query: str,
) -> None:
    response = await api_client.get(f"/conversations?{query}")
    assert response.status_code == 422
