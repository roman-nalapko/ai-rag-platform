import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.api import documents as documents_api
from app.services.knowledge_base import KnowledgeBaseNotFoundError

DOCUMENT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
KNOWLEDGE_BASE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def document_result_stub() -> SimpleNamespace:
    return SimpleNamespace(
        document=SimpleNamespace(
            id=DOCUMENT_ID,
            knowledge_base_id=KNOWLEDGE_BASE_ID,
            filename="document.txt",
            content_type="text/plain",
            created_at=datetime(2026, 8, 17, tzinfo=UTC),
            processed=True,
            status="indexed",
            error_message=None,
        ),
        chunks_count=5,
    )


@pytest.mark.asyncio
async def test_list_documents_returns_200(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_args: dict[str, Any] = {}

    class FakeDocumentService:
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
            return [document_result_stub()]

    monkeypatch.setattr(documents_api, "DocumentService", FakeDocumentService)

    response = await api_client.get(
        f"/documents?knowledge_base_id={KNOWLEDGE_BASE_ID}&limit=10&offset=5"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(DOCUMENT_ID)
    assert data[0]["filename"] == "document.txt"
    assert data[0]["chunks_count"] == 5
    assert data[0]["status"] == "indexed"
    assert captured_args["knowledge_base_id"] == KNOWLEDGE_BASE_ID
    assert captured_args["limit"] == 10
    assert captured_args["offset"] == 5


@pytest.mark.asyncio
async def test_list_documents_returns_404_when_knowledge_base_not_found(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDocumentService:
        def __init__(self, _: object) -> None:
            pass

        async def list_for_knowledge_base(
            self,
            knowledge_base_id: uuid.UUID,
            current_user_id: uuid.UUID,
            limit: int,
            offset: int,
        ) -> list[Any]:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")

    monkeypatch.setattr(documents_api, "DocumentService", FakeDocumentService)

    response = await api_client.get(f"/documents?knowledge_base_id={KNOWLEDGE_BASE_ID}")

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
async def test_list_documents_validates_query_params(
    api_client: httpx.AsyncClient,
    query: str,
) -> None:
    response = await api_client.get(f"/documents?{query}")
    assert response.status_code == 422
