from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.llm.lm_studio_client import (
    LMStudioClient,
    LMStudioClientError,
    get_lm_studio_client,
)
from app.schemas.health import LLMHealthResponse
from app.services.llm_health import LLMHealthService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health() -> dict[str, str]:
    return {
        "status": "running",
        "mode": "local-ai",
    }


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
