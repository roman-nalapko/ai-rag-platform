import uuid
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.metrics import metrics
from app.llm.lm_studio_client import (
    LMStudioClient,
    LMStudioClientError,
    get_lm_studio_client,
)
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import KnowledgeBase
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.reranker import Reranker, get_reranker
from app.rag.vector_store import (
    VectorSearchHit,
    VectorStoreError,
    VectorStoreService,
    get_vector_store,
)


class SearchLLMUnavailableError(RuntimeError):
    """Raised when a query embedding cannot be generated."""


class SearchVectorStoreError(RuntimeError):
    """Raised when semantic search cannot be completed in Qdrant."""


class SearchKnowledgeBaseNotFoundError(ValueError):
    """Raised when semantic search targets an unknown knowledge base."""


@dataclass(frozen=True, slots=True)
class SearchMatch:
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    filename: str
    content: str
    score: float


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: LMStudioClient,
        vector_store: VectorStoreService,
        reranker: Reranker,
    ) -> None:
        self._session = session
        self._embedding_client = embedding_client
        self._vector_store = vector_store
        self._reranker = reranker

    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> list[SearchMatch]:
        knowledge_base = await self._session.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base is None or knowledge_base.user_id != current_user_id:
            raise SearchKnowledgeBaseNotFoundError("Knowledge base not found")

        # Do not hold a PostgreSQL transaction while waiting for local model
        # inference or Qdrant. QA generation can take minutes on small machines.
        await self._session.rollback()

        started_at = perf_counter()
        try:
            query_vector = await self._embedding_client.embed_text(query)
        except LMStudioClientError as error:
            raise SearchLLMUnavailableError("LM Studio is unavailable") from error

        try:
            hits = await self._vector_store.search(
                query_vector,
                self._candidate_limit(limit),
                knowledge_base_id,
            )
        except VectorStoreError as error:
            raise SearchVectorStoreError("Qdrant semantic search failed") from error

        matches = [self._to_match(hit, knowledge_base_id) for hit in hits]
        reranked = self._reranker.rerank(query, matches, limit)
        metrics.search_duration_seconds.observe(perf_counter() - started_at)
        return reranked

    async def search_text(
        self,
        query: str,
        limit: int,
        knowledge_base_id: uuid.UUID,
    ) -> list[SearchMatch]:
        try:
            result = await self._session.execute(
                select(
                    DocumentChunk.id,
                    DocumentChunk.document_id,
                    DocumentChunk.chunk_index,
                    Document.filename,
                    DocumentChunk.content,
                )
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    Document.knowledge_base_id == knowledge_base_id,
                    func.to_tsvector("english", DocumentChunk.content).op("@@")(
                        func.plainto_tsquery("english", query)
                    ),
                )
                .limit(limit)
            )
            return [
                SearchMatch(
                    document_id=row[1],
                    chunk_id=row[0],
                    chunk_index=row[2],
                    filename=row[3],
                    content=row[4],
                    score=1.0,
                )
                for row in result.all()
            ]
        except Exception:
            return []

    async def search_hybrid(
        self,
        query: str,
        limit: int,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> list[SearchMatch]:
        dense_matches = await self.search(
            query=query,
            limit=limit * 2,
            knowledge_base_id=knowledge_base_id,
            current_user_id=current_user_id,
        )
        text_matches = await self.search_text(
            query=query,
            limit=limit * 2,
            knowledge_base_id=knowledge_base_id,
        )
        if not text_matches:
            return dense_matches[:limit]
        return reciprocal_rank_fusion(
            [dense_matches, text_matches],
            k=60,
            limit=limit,
        )

    @staticmethod
    def _candidate_limit(limit: int) -> int:
        if not settings.RERANKING_ENABLED:
            return limit
        return min(limit * settings.RERANKING_CANDIDATE_MULTIPLIER, 50)

    @staticmethod
    def _to_match(
        hit: VectorSearchHit,
        knowledge_base_id: uuid.UUID,
    ) -> SearchMatch:
        try:
            payload_knowledge_base_id = uuid.UUID(str(hit.payload["knowledge_base_id"]))
            if payload_knowledge_base_id != knowledge_base_id:
                raise ValueError("Knowledge base payload mismatch")

            return SearchMatch(
                document_id=uuid.UUID(str(hit.payload["document_id"])),
                chunk_id=uuid.UUID(str(hit.payload["chunk_id"])),
                chunk_index=int(hit.payload["chunk_index"]),
                filename=str(hit.payload["filename"]),
                content=str(hit.payload["content"]),
                score=hit.score,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SearchVectorStoreError(
                "Qdrant returned an invalid document chunk payload"
            ) from error


def get_search_service(session: AsyncSession) -> SearchService:
    return SearchService(
        session=session,
        embedding_client=get_lm_studio_client(),
        vector_store=get_vector_store(),
        reranker=get_reranker(),
    )
