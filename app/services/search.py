import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.lm_studio_client import (
    LMStudioClient,
    LMStudioClientError,
    get_lm_studio_client,
)
from app.models.knowledge_base import KnowledgeBase
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
    ) -> None:
        self._session = session
        self._embedding_client = embedding_client
        self._vector_store = vector_store

    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base_id: uuid.UUID,
    ) -> list[SearchMatch]:
        knowledge_base = await self._session.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base is None:
            raise SearchKnowledgeBaseNotFoundError("Knowledge base not found")

        # Do not hold a PostgreSQL transaction while waiting for local model
        # inference or Qdrant. QA generation can take minutes on small machines.
        await self._session.rollback()

        try:
            query_vector = await self._embedding_client.embed_text(query)
        except LMStudioClientError as error:
            raise SearchLLMUnavailableError("LM Studio is unavailable") from error

        try:
            hits = await self._vector_store.search(
                query_vector,
                limit,
                knowledge_base_id,
            )
        except VectorStoreError as error:
            raise SearchVectorStoreError("Qdrant semantic search failed") from error

        return [self._to_match(hit, knowledge_base_id) for hit in hits]

    @staticmethod
    def _to_match(
        hit: VectorSearchHit,
        knowledge_base_id: uuid.UUID,
    ) -> SearchMatch:
        try:
            payload_knowledge_base_id = uuid.UUID(
                str(hit.payload["knowledge_base_id"])
            )
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
    )
