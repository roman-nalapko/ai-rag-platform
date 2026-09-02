import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.qa import QARequest, QAResponse, QASourceResponse
from app.services.qa import (
    QAConversationNotFoundError,
    QAKnowledgeBaseNotFoundError,
    QALLMUnavailableError,
    QAVectorStoreError,
    get_qa_service,
)

router = APIRouter(prefix="/qa", tags=["Question Answering"])


def _format_typed_sse(event_type: str, data: Any) -> str:
    if isinstance(data, (dict, list)):
        payload = json.dumps(data, ensure_ascii=False)
    else:
        payload = str(data)
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    formatted_data = normalized.replace("\n", "\ndata: ")
    return f"event: {event_type}\ndata: {formatted_data}\n\n"


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> QAResponse:
    service = get_qa_service(session)
    try:
        result = await service.ask(
            request.question,
            request.limit,
            request.knowledge_base_id,
            current_user.id,
            request.conversation_id,
            hybrid=request.hybrid,
        )
    except (QAKnowledgeBaseNotFoundError, QAConversationNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except QALLMUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except QAVectorStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    return QAResponse(
        question=result.question,
        answer=result.answer,
        sources=[
            QASourceResponse(
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                filename=source.filename,
                chunk_index=source.chunk_index,
                score=source.score,
                content=source.content,
            )
            for source in result.sources
        ],
    )


@router.post(
    "/ask/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_answer(
    request: QARequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    service = get_qa_service(session)
    try:
        events = await service.stream_events(
            request.question,
            request.limit,
            request.knowledge_base_id,
            current_user.id,
            request.conversation_id,
            hybrid=request.hybrid,
        )
    except (QAKnowledgeBaseNotFoundError, QAConversationNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except QALLMUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except QAVectorStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    async def event_stream() -> AsyncIterator[str]:
        async for event in events:
            yield _format_typed_sse(event.event, event.data)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
