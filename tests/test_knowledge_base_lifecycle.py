import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.api import knowledge_bases as knowledge_bases_api
from app.services.knowledge_base import KnowledgeBaseNotFoundError

KNOWLEDGE_BASE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def knowledge_base_stub() -> SimpleNamespace:
    return SimpleNamespace(
        id=KNOWLEDGE_BASE_ID,
        user_id=USER_ID,
        name="Engineering Docs",
        description="Backend documentation",
        created_at=datetime(2026, 8, 17, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_get_knowledge_base_returns_200(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKnowledgeBaseService:
        def __init__(self, _: object) -> None:
            pass

        async def get(
            self,
            knowledge_base_id: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> Any:
            assert knowledge_base_id == KNOWLEDGE_BASE_ID
            return knowledge_base_stub()

    monkeypatch.setattr(
        knowledge_bases_api,
        "KnowledgeBaseService",
        FakeKnowledgeBaseService,
    )

    response = await api_client.get(f"/knowledge-bases/{KNOWLEDGE_BASE_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(KNOWLEDGE_BASE_ID)
    assert data["name"] == "Engineering Docs"


@pytest.mark.asyncio
async def test_get_knowledge_base_returns_404_when_missing(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKnowledgeBaseService:
        def __init__(self, _: object) -> None:
            pass

        async def get(
            self,
            knowledge_base_id: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> Any:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")

    monkeypatch.setattr(
        knowledge_bases_api,
        "KnowledgeBaseService",
        FakeKnowledgeBaseService,
    )

    response = await api_client.get(f"/knowledge-bases/{KNOWLEDGE_BASE_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Knowledge base not found"}


@pytest.mark.asyncio
async def test_delete_knowledge_base_returns_204(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted_ids: list[uuid.UUID] = []

    class FakeKnowledgeBaseService:
        def __init__(self, _: object) -> None:
            pass

        async def delete(
            self,
            knowledge_base_id: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> None:
            deleted_ids.append(knowledge_base_id)

    monkeypatch.setattr(
        knowledge_bases_api,
        "KnowledgeBaseService",
        FakeKnowledgeBaseService,
    )

    response = await api_client.delete(f"/knowledge-bases/{KNOWLEDGE_BASE_ID}")

    assert response.status_code == 204
    assert deleted_ids == [KNOWLEDGE_BASE_ID]


@pytest.mark.asyncio
async def test_delete_knowledge_base_returns_404_when_missing(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKnowledgeBaseService:
        def __init__(self, _: object) -> None:
            pass

        async def delete(
            self,
            knowledge_base_id: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> None:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")

    monkeypatch.setattr(
        knowledge_bases_api,
        "KnowledgeBaseService",
        FakeKnowledgeBaseService,
    )

    response = await api_client.delete(f"/knowledge-bases/{KNOWLEDGE_BASE_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Knowledge base not found"}
