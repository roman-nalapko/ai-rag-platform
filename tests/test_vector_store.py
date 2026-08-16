import uuid
from types import SimpleNamespace
from typing import cast

import pytest

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.vector_store import VectorStoreService


def test_qdrant_point_payload_includes_embedding_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "LM_STUDIO_EMBEDDING_MODEL",
        "test-embedding-model",
    )

    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    document = cast(
        Document,
        SimpleNamespace(
            id=document_id,
            knowledge_base_id=knowledge_base_id,
            filename="document.txt",
        ),
    )
    chunk = cast(
        DocumentChunk,
        SimpleNamespace(
            id=chunk_id,
            chunk_index=0,
            content="Chunk content",
        ),
    )

    point = VectorStoreService._build_point(
        document=document,
        chunk=chunk,
        embedding=[0.1, 0.2, 0.3],
    )

    assert point.payload == {
        "knowledge_base_id": str(knowledge_base_id),
        "document_id": str(document_id),
        "chunk_id": str(chunk_id),
        "chunk_index": 0,
        "embedding_model": "test-embedding-model",
        "filename": "document.txt",
        "content": "Chunk content",
    }
