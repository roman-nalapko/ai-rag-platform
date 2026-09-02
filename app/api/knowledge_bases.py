import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.rag.vector_store import VectorStoreError
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services.knowledge_base import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
    UserNotFoundError,
)

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Bases"])


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    request: KnowledgeBaseCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> KnowledgeBaseResponse:
    try:
        knowledge_base = await KnowledgeBaseService(session).create(
            user_id=request.user_id,
            name=request.name,
            description=request.description,
            current_user_id=current_user.id,
        )
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except KnowledgeBaseAccessDeniedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    user_id: Annotated[uuid.UUID, Query(description="Knowledge base owner")],
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
) -> list[KnowledgeBaseResponse]:
    try:
        knowledge_bases = await KnowledgeBaseService(session).list_for_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
            current_user_id=current_user.id,
        )
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except KnowledgeBaseAccessDeniedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    return [
        KnowledgeBaseResponse.model_validate(knowledge_base)
        for knowledge_base in knowledge_bases
    ]


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    knowledge_base_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> KnowledgeBaseResponse:
    try:
        knowledge_base = await KnowledgeBaseService(session).get(
            knowledge_base_id=knowledge_base_id,
            current_user_id=current_user.id,
        )
    except KnowledgeBaseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    knowledge_base_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    try:
        await KnowledgeBaseService(session).delete(
            knowledge_base_id=knowledge_base_id,
            current_user_id=current_user.id,
        )
    except KnowledgeBaseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except VectorStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
