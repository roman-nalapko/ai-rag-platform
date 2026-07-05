import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


class UserNotFoundError(ValueError):
    """Raised when a knowledge base owner does not exist."""


class KnowledgeBaseNotFoundError(ValueError):
    """Raised when a requested knowledge base does not exist."""


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> KnowledgeBase:
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

    async def list_for_user(self, user_id: uuid.UUID) -> list[KnowledgeBase]:
        if await self._session.get(User, user_id) is None:
            raise UserNotFoundError("User not found")

        result = await self._session.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at, KnowledgeBase.id)
        )
        return list(result.scalars().all())
