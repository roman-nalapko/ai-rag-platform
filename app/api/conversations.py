import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
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


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    knowledge_base_id: Annotated[
        uuid.UUID,
        Query(description="Knowledge base ID to list conversations from"),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of records to return"),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of records to skip"),
    ] = 0,
) -> list[ConversationResponse]:
    try:
        conversations = await ConversationService(session).list_for_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            current_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except ConversationKnowledgeBaseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return [
        ConversationResponse.model_validate(conversation)
        for conversation in conversations
    ]


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationResponse:
    try:
        conversation = await ConversationService(session).create(
            knowledge_base_id=request.knowledge_base_id,
            title=request.title,
            current_user_id=current_user.id,
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
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MessageResponse]:
    try:
        messages = await ConversationService(session).get_messages(
            conversation_id,
            current_user.id,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return [MessageResponse.model_validate(message) for message in messages]
