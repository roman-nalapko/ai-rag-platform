import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update

from app.core.config import settings
from app.core.metrics import metrics
from app.db.session import AsyncSessionFactory
from app.models.document import Document, DocumentStatus
from app.models.document_job import DocumentJob, DocumentJobStatus
from app.services.document import DocumentService

logger = logging.getLogger(__name__)


class DocumentWorker:
    def __init__(self, poll_seconds: float | None = None) -> None:
        self._poll_seconds = poll_seconds or settings.DOCUMENT_WORKER_POLL_SECONDS

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        await self.recover_processing_jobs()
        while not stop_event.is_set():
            processed = await self.run_once()
            if processed:
                continue
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._poll_seconds)
            except TimeoutError:
                continue

    async def run_once(self) -> bool:
        claimed = await self._claim_next_job()
        if claimed is None:
            return False

        job_id, document_id = claimed
        logger.info(
            "document_job_started",
            extra={
                "operation": "document_job",
                "job_id": job_id,
                "document_id": document_id,
            },
        )
        try:
            async with AsyncSessionFactory() as session:
                await DocumentService(session).process_pending(document_id)
        except Exception:
            logger.exception(
                "Unhandled exception during document processing",
                extra={
                    "job_id": str(job_id),
                    "document_id": str(document_id),
                },
            )
        finally:
            await self._complete_job(job_id, document_id)
        return True

    async def recover_processing_jobs(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.DOCUMENT_WORKER_STALE_AFTER_SECONDS
        )
        async with AsyncSessionFactory() as session:
            stale_document_ids = select(DocumentJob.document_id).where(
                DocumentJob.status == DocumentJobStatus.PROCESSING.value,
                or_(
                    DocumentJob.started_at.is_(None),
                    DocumentJob.started_at < cutoff,
                ),
            )
            # Reset documents first: the subquery intentionally still sees the
            # jobs in their processing state inside this transaction.
            await session.execute(
                update(Document)
                .where(
                    Document.status == DocumentStatus.PROCESSING.value,
                    Document.id.in_(stale_document_ids),
                )
                .values(
                    status=DocumentStatus.PENDING.value,
                    processed=False,
                    error_message=None,
                )
            )
            await session.execute(
                update(DocumentJob)
                .where(
                    DocumentJob.status == DocumentJobStatus.PROCESSING.value,
                    or_(
                        DocumentJob.started_at.is_(None),
                        DocumentJob.started_at < cutoff,
                    ),
                )
                .values(
                    status=DocumentJobStatus.PENDING.value,
                    error_message=None,
                    started_at=None,
                    completed_at=None,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()

    async def _claim_next_job(self) -> tuple[uuid.UUID, uuid.UUID] | None:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(DocumentJob)
                .where(DocumentJob.status == DocumentJobStatus.PENDING.value)
                .order_by(DocumentJob.created_at, DocumentJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job = result.scalar_one_or_none()
            if job is None:
                await session.rollback()
                return None

            job.status = DocumentJobStatus.PROCESSING.value
            job.attempts += 1
            job.started_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            job.error_message = None
            job_id = job.id
            document_id = job.document_id
            await session.commit()
            return job_id, document_id

    async def _complete_job(
        self,
        job_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        async with AsyncSessionFactory() as session:
            job = await session.get(DocumentJob, job_id)
            document = await session.get(Document, document_id)
            if job is None:
                return

            completed_at = datetime.now(UTC)
            if document is not None and document.status == DocumentStatus.INDEXED.value:
                job.status = DocumentJobStatus.COMPLETED.value
                job.error_message = None
                outcome = "completed"
            else:
                job.status = DocumentJobStatus.FAILED.value
                job.error_message = (
                    document.error_message
                    if document is not None and document.error_message
                    else "Document indexing failed"
                )
                outcome = "failed"

            if job.started_at is not None:
                duration_seconds = (completed_at - job.started_at).total_seconds()
                metrics.document_indexing_duration_seconds.observe(
                    max(duration_seconds, 0.0),
                    outcome=outcome,
                )
            metrics.document_jobs_total.inc(outcome=outcome)

            job.completed_at = completed_at
            job.updated_at = completed_at
            await session.commit()


async def run_document_worker() -> None:
    stop_event = asyncio.Event()
    await DocumentWorker().run_forever(stop_event)
