import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.document import DocumentDetailResponse, DocumentUploadResponse
from app.services.document import (
    DocumentNotFoundError,
    DocumentService,
    DocumentStorageError,
    InvalidFilenameError,
    UnsupportedDocumentTypeError,
    process_document_background,
)
from app.services.knowledge_base import KnowledgeBaseNotFoundError

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF or plain-text document")],
    knowledge_base_id: Annotated[
        uuid.UUID,
        Form(description="Destination knowledge base ID"),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentUploadResponse:
    try:
        result = await DocumentService(session).create_from_upload(
            file,
            knowledge_base_id,
        )
    except InvalidFilenameError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except UnsupportedDocumentTypeError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    except KnowledgeBaseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    finally:
        await file.close()

    background_tasks.add_task(
        process_document_background,
        result.document.id,
    )

    return DocumentUploadResponse(
        id=result.document.id,
        knowledge_base_id=result.document.knowledge_base_id,
        filename=result.document.filename,
        content_type=result.document.content_type,
        created_at=result.document.created_at,
        processed=result.document.processed,
        status=result.document.status,
        error_message=result.document.error_message,
        chunks_count=result.chunks_count,
        indexed=False,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentDetailResponse:
    try:
        result = await DocumentService(session).get(document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return DocumentDetailResponse(
        id=result.document.id,
        knowledge_base_id=result.document.knowledge_base_id,
        filename=result.document.filename,
        content_type=result.document.content_type,
        created_at=result.document.created_at,
        processed=result.document.processed,
        status=result.document.status,
        error_message=result.document.error_message,
        chunks_count=result.chunks_count,
    )
