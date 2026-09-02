import uuid
from typing import Annotated, cast

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.rag.vector_store import VectorStoreError
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentStatusValue,
    DocumentUploadResponse,
)
from app.services.document import (
    DocumentAlreadyProcessingError,
    DocumentNotFoundError,
    DocumentService,
    DocumentStorageError,
    DocumentTooLargeError,
    InvalidFilenameError,
    UnsupportedDocumentTypeError,
)
from app.services.knowledge_base import KnowledgeBaseNotFoundError

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=list[DocumentDetailResponse])
async def list_documents(
    knowledge_base_id: Annotated[
        uuid.UUID,
        Query(description="Knowledge base ID to list documents from"),
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
) -> list[DocumentDetailResponse]:
    try:
        results = await DocumentService(session).list_for_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            current_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except KnowledgeBaseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return [
        DocumentDetailResponse(
            id=result.document.id,
            knowledge_base_id=result.document.knowledge_base_id,
            filename=result.document.filename,
            content_type=result.document.content_type,
            created_at=result.document.created_at,
            processed=result.document.processed,
            status=cast(DocumentStatusValue, result.document.status),
            error_message=result.document.error_message,
            chunks_count=result.chunks_count,
        )
        for result in results
    ]


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF or plain-text document")],
    knowledge_base_id: Annotated[
        uuid.UUID,
        Form(description="Destination knowledge base ID"),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentUploadResponse:
    try:
        result = await DocumentService(session).create_from_upload(
            file,
            knowledge_base_id,
            current_user.id,
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
    except DocumentTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
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

    return DocumentUploadResponse(
        id=result.document.id,
        knowledge_base_id=result.document.knowledge_base_id,
        filename=result.document.filename,
        content_type=result.document.content_type,
        created_at=result.document.created_at,
        processed=result.document.processed,
        status=cast(DocumentStatusValue, result.document.status),
        error_message=result.document.error_message,
        chunks_count=result.chunks_count,
        indexed=False,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentDetailResponse:
    try:
        result = await DocumentService(session).get(document_id, current_user.id)
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
        status=cast(DocumentStatusValue, result.document.status),
        error_message=result.document.error_message,
        chunks_count=result.chunks_count,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    try:
        await DocumentService(session).delete(document_id, current_user.id)
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentAlreadyProcessingError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except VectorStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error


@router.post("/{document_id}/reindex", response_model=DocumentDetailResponse)
async def reindex_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentDetailResponse:
    try:
        result = await DocumentService(session).enqueue_reindex(
            document_id,
            current_user.id,
        )
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentAlreadyProcessingError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except VectorStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    return DocumentDetailResponse(
        id=result.document.id,
        knowledge_base_id=result.document.knowledge_base_id,
        filename=result.document.filename,
        content_type=result.document.content_type,
        created_at=result.document.created_at,
        processed=result.document.processed,
        status=cast(DocumentStatusValue, result.document.status),
        error_message=result.document.error_message,
        chunks_count=result.chunks_count,
    )
