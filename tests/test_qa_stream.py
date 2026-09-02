import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from app.api import qa as qa_api
from app.services.qa import (
    QAConversationNotFoundError,
    QAKnowledgeBaseNotFoundError,
    QALLMUnavailableError,
    QAStreamEvent,
    QAVectorStoreError,
)

KNOWLEDGE_BASE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CONVERSATION_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")


@pytest.mark.asyncio
async def test_stream_answer_emits_typed_sse_events(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeQAService:
        async def stream_events(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[QAStreamEvent]:
            async def _gen() -> AsyncIterator[QAStreamEvent]:
                yield QAStreamEvent(
                    event="sources",
                    data=[
                        {
                            "document_id": "11111111-1111-4111-8111-111111111111",
                            "chunk_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                            "filename": "sample.txt",
                            "chunk_index": 0,
                            "score": 0.95,
                            "content": "Sample content about RAG.",
                        }
                    ],
                )
                yield QAStreamEvent(event="token", data="This ")
                yield QAStreamEvent(event="token", data="is an answer.")
                yield QAStreamEvent(
                    event="done",
                    data={"answer": "This is an answer.", "sources_count": 1},
                )

            return _gen()

    monkeypatch.setattr(qa_api, "get_qa_service", lambda _: FakeQAService())

    response = await api_client.post(
        "/qa/ask/stream",
        json={
            "knowledge_base_id": str(KNOWLEDGE_BASE_ID),
            "question": "What is RAG?",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    content = response.text
    assert "event: sources" in content
    assert "event: token" in content
    assert "data: This " in content
    assert "data: is an answer." in content
    assert "event: done" in content
    assert "data: [DONE]" in content


@pytest.mark.asyncio
async def test_stream_answer_maps_404_when_knowledge_base_missing(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeQAService:
        async def stream_events(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[QAStreamEvent]:
            raise QAKnowledgeBaseNotFoundError("Knowledge base not found")

    monkeypatch.setattr(qa_api, "get_qa_service", lambda _: FakeQAService())

    response = await api_client.post(
        "/qa/ask/stream",
        json={
            "knowledge_base_id": str(KNOWLEDGE_BASE_ID),
            "question": "What is RAG?",
            "limit": 5,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Knowledge base not found"}


@pytest.mark.asyncio
async def test_stream_answer_maps_404_when_conversation_missing(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeQAService:
        async def stream_events(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[QAStreamEvent]:
            raise QAConversationNotFoundError("Conversation not found")

    monkeypatch.setattr(qa_api, "get_qa_service", lambda _: FakeQAService())

    response = await api_client.post(
        "/qa/ask/stream",
        json={
            "knowledge_base_id": str(KNOWLEDGE_BASE_ID),
            "conversation_id": str(CONVERSATION_ID),
            "question": "What is RAG?",
            "limit": 5,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}


@pytest.mark.asyncio
async def test_stream_answer_maps_503_when_llm_unavailable(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeQAService:
        async def stream_events(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[QAStreamEvent]:
            raise QALLMUnavailableError("LM Studio is unavailable")

    monkeypatch.setattr(qa_api, "get_qa_service", lambda _: FakeQAService())

    response = await api_client.post(
        "/qa/ask/stream",
        json={
            "knowledge_base_id": str(KNOWLEDGE_BASE_ID),
            "question": "What is RAG?",
            "limit": 5,
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "LM Studio is unavailable"}


@pytest.mark.asyncio
async def test_stream_answer_maps_500_when_vector_store_fails(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeQAService:
        async def stream_events(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[QAStreamEvent]:
            raise QAVectorStoreError("Qdrant semantic search failed")

    monkeypatch.setattr(qa_api, "get_qa_service", lambda _: FakeQAService())

    response = await api_client.post(
        "/qa/ask/stream",
        json={
            "knowledge_base_id": str(KNOWLEDGE_BASE_ID),
            "question": "What is RAG?",
            "limit": 5,
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Qdrant semantic search failed"}
