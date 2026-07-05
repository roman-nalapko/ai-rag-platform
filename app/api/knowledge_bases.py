import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services.knowledge_base import KnowledgeBaseService, UserNotFoundError

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Bases"])


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    request: KnowledgeBaseCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeBaseResponse:
    try:
        knowledge_base = await KnowledgeBaseService(session).create(
            user_id=request.user_id,
            name=request.name,
            description=request.description,
        )
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    user_id: Annotated[uuid.UUID, Query(description="Knowledge base owner")],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[KnowledgeBaseResponse]:
    try:
        knowledge_bases = await KnowledgeBaseService(session).list_for_user(user_id)
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return [
        KnowledgeBaseResponse.model_validate(knowledge_base)
        for knowledge_base in knowledge_bases
    ]
