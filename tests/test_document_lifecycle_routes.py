import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.api import documents as documents_api
from app.services.document import (
    DocumentAlreadyProcessingError,
    DocumentNotFoundError,
)

DOCUMENT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
KNOWLEDGE_BASE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def document_stub(status: str = "pending") -> SimpleNamespace:
    return SimpleNamespace(
        id=DOCUMENT_ID,
        knowledge_base_id=KNOWLEDGE_BASE_ID,
        filename="document.txt",
        content_type="text/plain",
        created_at=datetime(2026, 8, 17, tzinfo=UTC),
        processed=False,
        status=status,
        error_message=None,
    )


def document_result(status: str = "pending") -> SimpleNamespace:
    return SimpleNamespace(
        document=document_stub(status),
        chunks_count=0,
    )


async def noop_background(_: uuid.UUID) -> None:
    return None


@pytest.mark.asyncio
async def test_delete_document_returns_204(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted_ids: list[uuid.UUID] = []

    class FakeDocumentService:
        def __init__(self, _: object) -> None:
            pass

        async def delete(
            self,
            document_id: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> None:
            deleted_ids.append(document_id)

    monkeypatch.setattr(documents_api, "DocumentService", FakeDocumentService)

    response = await api_client.delete(f"/documents/{DOCUMENT_ID}")

    assert response.status_code == 204
    assert deleted_ids == [DOCUMENT_ID]


@pytest.mark.asyncio
async def test_delete_document_returns_404_when_missing(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDocumentService:
        def __init__(self, _: object) -> None:
            pass

        async def delete(
            self,
            _: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> None:
            raise DocumentNotFoundError("Document not found")

    monkeypatch.setattr(documents_api, "DocumentService", FakeDocumentService)

    response = await api_client.delete(f"/documents/{DOCUMENT_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


@pytest.mark.asyncio
async def test_reindex_document_returns_pending_document(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reindexed_ids: list[uuid.UUID] = []
    background_ids: list[uuid.UUID] = []

    class FakeDocumentService:
        def __init__(self, _: object) -> None:
            pass

        async def enqueue_reindex(
            self,
            document_id: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> Any:
            reindexed_ids.append(document_id)
            return document_result()

    async def fake_background(document_id: uuid.UUID) -> None:
        background_ids.append(document_id)

    monkeypatch.setattr(documents_api, "DocumentService", FakeDocumentService)
    monkeypatch.setattr(documents_api, "process_document_background", fake_background)

    response = await api_client.post(f"/documents/{DOCUMENT_ID}/reindex")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["chunks_count"] == 0
    assert reindexed_ids == [DOCUMENT_ID]
    assert background_ids == [DOCUMENT_ID]


@pytest.mark.asyncio
async def test_reindex_document_returns_409_when_processing(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDocumentService:
        def __init__(self, _: object) -> None:
            pass

        async def enqueue_reindex(
            self,
            _: uuid.UUID,
            current_user_id: uuid.UUID,
        ) -> Any:
            raise DocumentAlreadyProcessingError(
                "Document is currently being processed"
            )

    monkeypatch.setattr(documents_api, "DocumentService", FakeDocumentService)
    monkeypatch.setattr(documents_api, "process_document_background", noop_background)

    response = await api_client.post(f"/documents/{DOCUMENT_ID}/reindex")

    assert response.status_code == 409
    assert response.json() == {"detail": "Document is currently being processed"}
