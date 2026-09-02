import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.rag.vector_store import VectorStoreError, VectorStoreService, get_vector_store


class UserNotFoundError(ValueError):
    """Raised when a knowledge base owner does not exist."""


class KnowledgeBaseNotFoundError(ValueError):
    """Raised when a requested knowledge base does not exist."""


class KnowledgeBaseAccessDeniedError(ValueError):
    """Raised when the authenticated user targets another user's data."""


class KnowledgeBaseService:
    def __init__(
        self,
        session: AsyncSession,
        vector_store: VectorStoreService | None = None,
        storage_path: Path | None = None,
    ) -> None:
        self._session = session
        self._vector_store = vector_store
        self._storage_path = storage_path or settings.UPLOAD_STORAGE_PATH

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        description: str | None,
        current_user_id: uuid.UUID,
    ) -> KnowledgeBase:
        if user_id != current_user_id:
            raise KnowledgeBaseAccessDeniedError("Knowledge base owner mismatch")
        if await self._session.get(User, user_id) is None:
            raise UserNotFoundError("User not found")

        knowledge_base = KnowledgeBase(
            user_id=user_id,
            name=name,
            description=description,
        )
        self._session.add(knowledge_base)

        try:
            await self._session.commit()
            await self._session.refresh(knowledge_base)
        except Exception:
            await self._session.rollback()
            raise

        return knowledge_base

    async def get(
        self,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> KnowledgeBase:
        knowledge_base = await self._session.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base is None or knowledge_base.user_id != current_user_id:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")
        return knowledge_base

    async def delete(
        self,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> None:
        knowledge_base = await self._session.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base is None or knowledge_base.user_id != current_user_id:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")

        result = await self._session.execute(
            select(Document.id, Document.filename).where(
                Document.knowledge_base_id == knowledge_base_id
            )
        )
        documents_to_delete = result.all()

        try:
            await self._get_vector_store().delete_knowledge_base_chunks(
                knowledge_base_id
            )
            await self._session.delete(knowledge_base)
            await self._session.commit()
        except VectorStoreError:
            await self._session.rollback()
            raise
        except Exception:
            await self._session.rollback()
            raise

        for doc_id, filename in documents_to_delete:
            storage_file = (
                self._storage_path / f"{doc_id}{Path(filename).suffix.lower()}"
            )
            await asyncio.to_thread(storage_file.unlink, missing_ok=True)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
        current_user_id: uuid.UUID,
    ) -> list[KnowledgeBase]:
        if user_id != current_user_id:
            raise KnowledgeBaseAccessDeniedError("Knowledge base owner mismatch")
        if await self._session.get(User, user_id) is None:
            raise UserNotFoundError("User not found")

        result = await self._session.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at, KnowledgeBase.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    def _get_vector_store(self) -> VectorStoreService:
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store
