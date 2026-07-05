import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
)
from app.services.conversation import (
    ConversationKnowledgeBaseNotFoundError,
    ConversationNotFoundError,
    ConversationService,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationResponse:
    try:
        conversation = await ConversationService(session).create(
            knowledge_base_id=request.knowledge_base_id,
            title=request.title,
        )
    except ConversationKnowledgeBaseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MessageResponse]:
    try:
        messages = await ConversationService(session).get_messages(conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return [MessageResponse.model_validate(message) for message in messages]
