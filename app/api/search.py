from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResultResponse
from app.services.search import (
    SearchKnowledgeBaseNotFoundError,
    SearchLLMUnavailableError,
    SearchVectorStoreError,
    get_search_service,
)

router = APIRouter(tags=["Search"])


@router.post("/search", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SearchResponse:
    service = get_search_service(session)
    try:
        matches = await service.search(
            request.query,
            request.limit,
            request.knowledge_base_id,
        )
    except SearchKnowledgeBaseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SearchLLMUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except SearchVectorStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    return SearchResponse(
        query=request.query,
        results=[
            SearchResultResponse(
                document_id=match.document_id,
                chunk_id=match.chunk_id,
                chunk_index=match.chunk_index,
                filename=match.filename,
                content=match.content,
                score=match.score,
            )
            for match in matches
        ],
    )
