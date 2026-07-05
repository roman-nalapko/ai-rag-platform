import asyncio
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import elapsed_ms
from app.db.session import AsyncSessionFactory
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import KnowledgeBase
from app.rag.vector_store import VectorStoreError, VectorStoreService, get_vector_store
from app.services.chunking import TextChunkingService
from app.services.knowledge_base import KnowledgeBaseNotFoundError
from app.services.text_extraction import DocumentExtractionError, TextExtractionService

ALLOWED_DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}

logger = logging.getLogger(__name__)


class UnsupportedDocumentTypeError(ValueError):
    """Raised when an uploaded document is not a supported PDF or TXT file."""


class InvalidFilenameError(ValueError):
    """Raised when an uploaded document has no valid filename."""


class DocumentNotFoundError(ValueError):
    """Raised when a requested document does not exist."""


class DocumentStorageError(RuntimeError):
    """Raised when a raw upload cannot be persisted."""


@dataclass(frozen=True, slots=True)
class DocumentResult:
    document: Document
    chunks_count: int


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        extraction_service: TextExtractionService | None = None,
        chunking_service: TextChunkingService | None = None,
        vector_store: VectorStoreService | None = None,
        storage_path: Path | None = None,
    ) -> None:
        self._session = session
        self._extraction_service = extraction_service or TextExtractionService()
        self._chunking_service = chunking_service or TextChunkingService(
            chunk_size=1000,
            chunk_overlap=200,
        )
        self._vector_store = vector_store
        self._storage_path = storage_path or settings.UPLOAD_STORAGE_PATH

    async def create_from_upload(
        self,
        file: UploadFile,
        knowledge_base_id: uuid.UUID,
    ) -> DocumentResult:
        filename = self._normalize_filename(file.filename)
        content_type = self._validate_content_type(filename, file.content_type)
        if await self._session.get(KnowledgeBase, knowledge_base_id) is None:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")

        document = Document(
            id=uuid.uuid4(),
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            content_type=content_type,
            processed=False,
            status=DocumentStatus.PENDING.value,
            error_message=None,
        )
        storage_file = self._storage_file(document.id, filename)

        try:
            await self._store_upload(file, storage_file)
            self._session.add(document)
            await self._session.commit()
        except DocumentStorageError:
            await self._session.rollback()
            raise
        except Exception:
            await self._session.rollback()
            await asyncio.to_thread(storage_file.unlink, missing_ok=True)
            raise

        return DocumentResult(document=document, chunks_count=0)

    async def get(self, document_id: uuid.UUID) -> DocumentResult:
        document = await self._session.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found")

        chunks_count = await self._session.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        return DocumentResult(
            document=document,
            chunks_count=int(chunks_count or 0),
        )

    async def process_pending(self, document_id: uuid.UUID) -> None:
        if not await self._claim_pending_document(document_id):
            return

        document = await self._session.get(Document, document_id)
        if document is None:
            return

        knowledge_base_id = document.knowledge_base_id
        started_at = perf_counter()
        chunks_count = 0
        logger.info(
            "document_indexing_started",
            extra={
                "operation": "document_indexing",
                "document_id": document_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        qdrant_indexed = False
        try:
            text = await self._extraction_service.extract_path(
                self._storage_file(document.id, document.filename),
                document.content_type,
            )
            chunk_contents = self._chunking_service.split(text)
            if not chunk_contents:
                raise DocumentExtractionError(
                    "Document contains no extractable text"
                )
            chunks_count = len(chunk_contents)

            chunks = [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                )
                for index, content in enumerate(chunk_contents)
            ]
            self._session.add_all(chunks)
            await self._session.flush()

            await self._get_vector_store().index_document_chunks(document, chunks)
            qdrant_indexed = True
            document.status = DocumentStatus.INDEXED.value
            document.processed = True
            document.error_message = None
            await self._session.commit()
            logger.info(
                "document_indexing_completed",
                extra={
                    "operation": "document_indexing",
                    "outcome": "completed",
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "chunks_count": chunks_count,
                    "duration_ms": elapsed_ms(started_at),
                },
            )
        except Exception as error:
            await self._session.rollback()
            if qdrant_indexed:
                await self._compensate_qdrant(document_id)
            await self._mark_failed(document_id, error)
            logger.exception(
                "document_indexing_failed",
                extra={
                    "operation": "document_indexing",
                    "outcome": "failed",
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "chunks_count": chunks_count,
                    "duration_ms": elapsed_ms(started_at),
                },
            )

    async def _claim_pending_document(self, document_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(Document)
            .where(
                Document.id == document_id,
                Document.status == DocumentStatus.PENDING.value,
            )
            .values(
                status=DocumentStatus.PROCESSING.value,
                processed=False,
                error_message=None,
            )
            .returning(Document.id)
        )
        claimed = result.scalar_one_or_none() is not None
        await self._session.commit()
        return claimed

    async def _mark_failed(
        self,
        document_id: uuid.UUID,
        error: Exception,
    ) -> None:
        document = await self._session.get(Document, document_id)
        if document is None:
            return

        document.status = DocumentStatus.FAILED.value
        document.processed = False
        document.error_message = self._public_error_message(error)
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            logger.exception(
                "Failed to persist processing error for document %s",
                document_id,
            )

    async def _compensate_qdrant(self, document_id: uuid.UUID) -> None:
        try:
            await self._get_vector_store().delete_document_chunks(document_id)
        except VectorStoreError:
            logger.exception(
                "Failed to remove vectors after database rollback for document %s",
                document_id,
            )

    async def _store_upload(self, file: UploadFile, destination: Path) -> None:
        await file.seek(0)
        try:
            await asyncio.to_thread(
                self._copy_upload,
                file.file,
                destination,
            )
        except OSError as error:
            raise DocumentStorageError("Uploaded file could not be stored") from error

    def _storage_file(self, document_id: uuid.UUID, filename: str) -> Path:
        return self._storage_path / f"{document_id}{Path(filename).suffix.lower()}"

    @staticmethod
    def _copy_upload(source: BinaryIO, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.part")
        try:
            with temporary.open("wb") as output:
                shutil.copyfileobj(source, output)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _public_error_message(error: Exception) -> str:
        if isinstance(error, DocumentExtractionError):
            return str(error)[:4000]
        if isinstance(error, VectorStoreError):
            return "Document embedding or vector indexing failed"
        return "Unexpected document processing error"

    def _get_vector_store(self) -> VectorStoreService:
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    @staticmethod
    def _normalize_filename(filename: str | None) -> str:
        if not filename:
            raise InvalidFilenameError("The uploaded file must have a filename")

        normalized = Path(filename).name.strip()
        if not normalized or len(normalized) > 255:
            raise InvalidFilenameError(
                "The filename must contain between 1 and 255 characters"
            )

        return normalized

    @staticmethod
    def _validate_content_type(filename: str, content_type: str | None) -> str:
        suffix = Path(filename).suffix.lower()
        expected_content_type = ALLOWED_DOCUMENT_TYPES.get(suffix)

        if expected_content_type is None or content_type != expected_content_type:
            raise UnsupportedDocumentTypeError(
                "Only PDF (application/pdf) and TXT (text/plain) files are supported"
            )

        return expected_content_type


async def process_document_background(document_id: uuid.UUID) -> None:
    async with AsyncSessionFactory() as session:
        await DocumentService(session).process_pending(document_id)
