import asyncio
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.core.logging import elapsed_ms
from app.llm.lm_studio_client import LMStudioClient, get_lm_studio_client
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "document_chunks"


class VectorStoreError(RuntimeError):
    """Raised when document chunks cannot be indexed in Qdrant."""


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    payload: dict[str, Any]
    score: float


class VectorStoreService:
    def __init__(
        self,
        client: AsyncQdrantClient,
        embedding_client: LMStudioClient,
    ) -> None:
        self._client = client
        self._embedding_client = embedding_client
        self._collection_lock = asyncio.Lock()

    async def index_document_chunks(
        self,
        document: Document,
        chunks: Sequence[DocumentChunk],
    ) -> None:
        if not chunks:
            raise VectorStoreError("Cannot index a document without chunks")
        if document.id is None:
            raise VectorStoreError("Document must be flushed before indexing")

        try:
            embeddings = await self._create_embeddings(chunks)
            vector_size = len(embeddings[0])
            await self._ensure_collection(vector_size)

            points = [
                self._build_point(document, chunk, embedding)
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]

            try:
                await self._client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points,
                    wait=True,
                )
            except Exception:
                await self._best_effort_delete(document.id)
                raise
        except VectorStoreError:
            raise
        except Exception as error:
            raise VectorStoreError("Failed to index document chunks") from error

    async def delete_document_chunks(self, document_id: uuid.UUID) -> None:
        try:
            if not await self._client.collection_exists(COLLECTION_NAME):
                return

            await self._client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=self._document_filter(document_id),
                wait=True,
            )
        except Exception as error:
            raise VectorStoreError("Failed to delete document vectors") from error

    async def search(
        self,
        query_vector: list[float],
        limit: int,
        knowledge_base_id: uuid.UUID,
    ) -> list[VectorSearchHit]:
        if not query_vector:
            raise VectorStoreError("Search vector must not be empty")

        started_at = perf_counter()
        try:
            if not await self._client.collection_exists(COLLECTION_NAME):
                hits: list[VectorSearchHit] = []
            else:
                response = await self._client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=query_vector,
                    query_filter=self._knowledge_base_filter(knowledge_base_id),
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                )
                hits = [
                    VectorSearchHit(
                        payload=dict(point.payload or {}),
                        score=point.score,
                    )
                    for point in response.points
                ]
        except Exception as error:
            logger.warning(
                "qdrant_search_failed",
                extra={
                    "operation": "qdrant_search",
                    "outcome": "failed",
                    "knowledge_base_id": knowledge_base_id,
                    "limit": limit,
                    "duration_ms": elapsed_ms(started_at),
                },
            )
            raise VectorStoreError("Qdrant semantic search failed") from error

        logger.info(
            "qdrant_search_completed",
            extra={
                "operation": "qdrant_search",
                "outcome": "completed",
                "knowledge_base_id": knowledge_base_id,
                "limit": limit,
                "result_count": len(hits),
                "duration_ms": elapsed_ms(started_at),
            },
        )
        return hits

    async def close(self) -> None:
        await self._client.close()

    async def _create_embeddings(
        self,
        chunks: Sequence[DocumentChunk],
    ) -> list[list[float]]:
        first_embedding = await self._embedding_client.embed_text(chunks[0].content)
        if not first_embedding:
            raise VectorStoreError("LM Studio returned an empty embedding")

        vector_size = len(first_embedding)
        embeddings = [first_embedding]

        for chunk in chunks[1:]:
            embedding = await self._embedding_client.embed_text(chunk.content)
            if len(embedding) != vector_size:
                raise VectorStoreError(
                    "LM Studio returned embeddings with inconsistent dimensions"
                )
            embeddings.append(embedding)

        return embeddings

    async def _ensure_collection(self, vector_size: int) -> None:
        async with self._collection_lock:
            if not await self._client.collection_exists(COLLECTION_NAME):
                try:
                    await self._client.create_collection(
                        collection_name=COLLECTION_NAME,
                        vectors_config=models.VectorParams(
                            size=vector_size,
                            distance=models.Distance.COSINE,
                        ),
                    )
                except UnexpectedResponse as error:
                    # Another application worker may have created it concurrently.
                    if error.status_code != 409:
                        raise

            collection = await self._client.get_collection(COLLECTION_NAME)
            vectors_config = collection.config.params.vectors

            if not isinstance(vectors_config, models.VectorParams):
                raise VectorStoreError(
                    "The document_chunks collection must use an unnamed dense vector"
                )
            if vectors_config.size != vector_size:
                raise VectorStoreError(
                    "Embedding size does not match the existing Qdrant collection"
                )
            if vectors_config.distance != models.Distance.COSINE:
                raise VectorStoreError(
                    "The document_chunks collection must use cosine distance"
                )

    @staticmethod
    def _build_point(
        document: Document,
        chunk: DocumentChunk,
        embedding: list[float],
    ) -> models.PointStruct:
        if chunk.id is None:
            raise VectorStoreError("Chunks must be flushed before indexing")
        if document.knowledge_base_id is None:
            raise VectorStoreError("Document must belong to a knowledge base")

        return models.PointStruct(
            id=chunk.id,
            vector=embedding,
            payload={
                "knowledge_base_id": str(document.knowledge_base_id),
                "document_id": str(document.id),
                "chunk_id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "filename": document.filename,
                "content": chunk.content,
            },
        )

    @staticmethod
    def _document_filter(document_id: uuid.UUID) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document_id)),
                )
            ]
        )

    @staticmethod
    def _knowledge_base_filter(knowledge_base_id: uuid.UUID) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="knowledge_base_id",
                    match=models.MatchValue(value=str(knowledge_base_id)),
                )
            ]
        )

    async def _best_effort_delete(self, document_id: uuid.UUID) -> None:
        try:
            await self.delete_document_chunks(document_id)
        except VectorStoreError:
            logger.exception(
                "Failed to compensate Qdrant upsert for document %s",
                document_id,
            )


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStoreService:
    return VectorStoreService(
        client=AsyncQdrantClient(url=settings.QDRANT_URL, timeout=30),
        embedding_client=get_lm_studio_client(),
    )


async def close_vector_store() -> None:
    if get_vector_store.cache_info().currsize == 0:
        return

    vector_store = get_vector_store()
    await vector_store.close()
    get_vector_store.cache_clear()
