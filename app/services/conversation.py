import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message, MessageRole


class ConversationNotFoundError(ValueError):
    """Raised when a conversation does not exist in the requested scope."""


class ConversationKnowledgeBaseNotFoundError(ValueError):
    """Raised when a conversation targets an unknown knowledge base."""


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        knowledge_base_id: uuid.UUID,
        title: str | None,
        current_user_id: uuid.UUID,
    ) -> Conversation:
        knowledge_base = await self._session.get(KnowledgeBase, knowledge_base_id)
        if knowledge_base is None or knowledge_base.user_id != current_user_id:
            raise ConversationKnowledgeBaseNotFoundError("Knowledge base not found")

        conversation = Conversation(
            knowledge_base_id=knowledge_base_id,
            title=title,
        )
        self._session.add(conversation)

        try:
            await self._session.commit()
            await self._session.refresh(conversation)
        except Exception:
            await self._session.rollback()
            raise

        return conversation

    async def get_messages(
        self,
        conversation_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> list[Message]:
        if not await self._conversation_belongs_to_user(
            conversation_id,
            current_user_id,
        ):
            raise ConversationNotFoundError("Conversation not found")

        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )
        return list(result.scalars().all())

    async def get_recent_messages(
        self,
        conversation_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
        limit: int = 5,
    ) -> list[Message]:
        await self._require_scoped_conversation(
            conversation_id,
            knowledge_base_id,
            current_user_id,
        )
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def save_exchange(
        self,
        conversation_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
        question: str,
        answer: str,
    ) -> None:
        await self._require_scoped_conversation(
            conversation_id,
            knowledge_base_id,
            current_user_id,
        )
        created_at = datetime.now(UTC)
        self._session.add_all(
            [
                Message(
                    conversation_id=conversation_id,
                    role=MessageRole.USER.value,
                    content=question,
                    created_at=created_at,
                ),
                Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT.value,
                    content=answer,
                    created_at=created_at + timedelta(microseconds=1),
                ),
            ]
        )

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def _require_scoped_conversation(
        self,
        conversation_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Conversation:
        result = await self._session.execute(
            select(Conversation)
            .join(KnowledgeBase)
            .where(
                Conversation.id == conversation_id,
                Conversation.knowledge_base_id == knowledge_base_id,
                KnowledgeBase.user_id == current_user_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFoundError("Conversation not found")
        return conversation

    async def _conversation_belongs_to_user(
        self,
        conversation_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> bool:
        result = await self._session.execute(
            select(Conversation.id)
            .join(KnowledgeBase)
            .where(
                Conversation.id == conversation_id,
                KnowledgeBase.user_id == current_user_id,
            )
        )
        return result.scalar_one_or_none() is not None
