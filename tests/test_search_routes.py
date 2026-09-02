import uuid
from typing import Any

import httpx
import pytest

from app.api import search as search_api
from app.services.search import (
    SearchKnowledgeBaseNotFoundError,
    SearchLLMUnavailableError,
    SearchMatch,
    SearchVectorStoreError,
)

KNOWLEDGE_BASE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class FakeSearchService:
    def __init__(self) -> None:
        self.called_mode: str | None = None

    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> list[SearchMatch]:
        self.called_mode = "semantic"
        return [
            SearchMatch(
                document_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
                chunk_id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                chunk_index=0,
                filename="sample.txt",
                content="Dense semantic match.",
                score=0.91,
            )
        ]

    async def search_hybrid(
        self,
        query: str,
        limit: int,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> list[SearchMatch]:
        self.called_mode = "hybrid"
        return [
            SearchMatch(
                document_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
                chunk_id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
                chunk_index=1,
                filename="sample.txt",
                content="Hybrid RRF match.",
                score=0.98,
            )
        ]


@pytest.mark.asyncio
async def test_search_endpoint_semantic_mode(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeSearchService()
    monkeypatch.setattr(search_api, "get_search_service", lambda _: fake_service)

    response = await api_client.post(
        "/search",
        json={
            "knowledge_base_id": str(KNOWLEDGE_BASE_ID),
            "query": "vector databases",
            "limit": 3,
            "hybrid": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "vector databases"
    assert len(data["results"]) == 1
    assert data["results"][0]["content"] == "Dense semantic match."
    assert fake_service.called_mode == "semantic"


@pytest.mark.asyncio
async def test_search_endpoint_hybrid_mode(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeSearchService()
    monkeypatch.setattr(search_api, "get_search_service", lambda _: fake_service)

    response = await api_client.post(
        "/search",
        json={
            "knowledge_base_id": str(KNOWLEDGE_BASE_ID),
            "query": "vector databases",
            "limit": 3,
            "hybrid": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "vector databases"
    assert len(data["results"]) == 1
    assert data["results"][0]["content"] == "Hybrid RRF match."
    assert fake_service.called_mode == "hybrid"


@pytest.mark.asyncio
async def test_search_endpoint_error_mappings(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingSearchService:
        def __init__(self, exc: Exception) -> None:
            self._exc = exc

        async def search(self, *args: Any, **kwargs: Any) -> list[SearchMatch]:
            raise self._exc

    # 404
    monkeypatch.setattr(
        search_api,
        "get_search_service",
        lambda _: FailingSearchService(
            SearchKnowledgeBaseNotFoundError("Knowledge base not found")
        ),
    )
    res_404 = await api_client.post(
        "/search",
        json={"knowledge_base_id": str(KNOWLEDGE_BASE_ID), "query": "test"},
    )
    assert res_404.status_code == 404

    # 503
    monkeypatch.setattr(
        search_api,
        "get_search_service",
        lambda _: FailingSearchService(
            SearchLLMUnavailableError("Embedding service down")
        ),
    )
    res_503 = await api_client.post(
        "/search",
        json={"knowledge_base_id": str(KNOWLEDGE_BASE_ID), "query": "test"},
    )
    assert res_503.status_code == 503

    # 500
    monkeypatch.setattr(
        search_api,
        "get_search_service",
        lambda _: FailingSearchService(SearchVectorStoreError("Qdrant store failure")),
    )
    res_500 = await api_client.post(
        "/search",
        json={"knowledge_base_id": str(KNOWLEDGE_BASE_ID), "query": "test"},
    )
    assert res_500.status_code == 500
