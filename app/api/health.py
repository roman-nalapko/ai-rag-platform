from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.llm.lm_studio_client import (
    LMStudioClient,
    LMStudioClientError,
    get_lm_studio_client,
)
from app.rag.vector_store import VectorStoreService, get_vector_store
from app.schemas.health import LLMHealthResponse, ReadinessResponse
from app.services.llm_health import LLMHealthService
from app.services.readiness import ReadinessCheckError, ReadinessService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health() -> dict[str, str]:
    return {
        "status": "running",
        "mode": "local-ai",
    }


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    session: Annotated[AsyncSession, Depends(get_db)],
    vector_store: Annotated[VectorStoreService, Depends(get_vector_store)],
) -> ReadinessResponse:
    try:
        result = await ReadinessService(session, vector_store).check()
    except ReadinessCheckError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return ReadinessResponse(
        status=result.status,
        checks=result.checks,
    )


@router.get("/llm", response_model=LLMHealthResponse)
async def llm_health(
    client: Annotated[LMStudioClient, Depends(get_lm_studio_client)],
) -> LLMHealthResponse:
    try:
        result = await LLMHealthService(client).check()
    except LMStudioClientError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return LLMHealthResponse(
        status=result.status,
        provider=result.provider,
        embedding_dimensions=result.embedding_dimensions,
    )
