import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionFactory, dispose_database_engine
from app.services.document_worker import DocumentWorker

pytestmark = pytest.mark.integration


def integration_tests_enabled() -> bool:
    return os.getenv("RUN_INTEGRATION_TESTS") == "1"


@pytest.fixture(autouse=True)
def require_integration_flag() -> None:
    if not integration_tests_enabled():
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")


@pytest_asyncio.fixture(autouse=True)
async def reset_database_pool_after_test() -> None:
    yield
    await dispose_database_engine()


@pytest.mark.asyncio
async def test_postgres_migrations_and_document_chunk_persistence() -> None:
    user_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    email = f"integration-{user_id}@example.com"
    committed = False

    async with AsyncSessionFactory() as session:
        try:
            tables = await session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('users', 'knowledge_bases', 'documents', 'document_chunks')
                    """
                )
            )
            assert {row[0] for row in tables} == {
                "users",
                "knowledge_bases",
                "documents",
                "document_chunks",
            }

            await session.execute(
                text("INSERT INTO users (id, email) VALUES (:id, :email)"),
                {"id": user_id, "email": email},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO knowledge_bases (id, user_id, name)
                    VALUES (:id, :user_id, :name)
                    """
                ),
                {
                    "id": knowledge_base_id,
                    "user_id": user_id,
                    "name": "Integration KB",
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO documents (
                        id,
                        knowledge_base_id,
                        filename,
                        content_type,
                        processed,
                        status
                    )
                    VALUES (
                        :id,
                        :knowledge_base_id,
                        'integration.txt',
                        'text/plain',
                        true,
                        'indexed'
                    )
                    """
                ),
                {
                    "id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        id,
                        document_id,
                        chunk_index,
                        content
                    )
                    VALUES (:id, :document_id, 0, 'integration chunk')
                    """
                ),
                {"id": chunk_id, "document_id": document_id},
            )
            await session.commit()
            committed = True

            persisted = await session.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM document_chunks
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": document_id},
            )
            assert persisted == 1
        finally:
            if committed:
                await session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": user_id},
                )
                await session.commit()


@pytest.mark.asyncio
async def test_qdrant_vector_payload_filtering() -> None:
    collection_name = f"integration_document_chunks_{uuid.uuid4().hex}"
    knowledge_base_id = str(uuid.uuid4())
    other_knowledge_base_id = str(uuid.uuid4())

    client = AsyncQdrantClient(url=settings.QDRANT_URL, timeout=30)
    try:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=3,
                distance=models.Distance.COSINE,
            ),
        )
        await client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "knowledge_base_id": knowledge_base_id,
                        "content": "matching integration chunk",
                    },
                ),
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "knowledge_base_id": other_knowledge_base_id,
                        "content": "wrong tenant chunk",
                    },
                ),
            ],
            wait=True,
        )

        response = await client.query_points(
            collection_name=collection_name,
            query=[1.0, 0.0, 0.0],
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="knowledge_base_id",
                        match=models.MatchValue(value=knowledge_base_id),
                    )
                ]
            ),
            limit=10,
            with_payload=True,
            with_vectors=False,
        )

        assert len(response.points) == 1
        assert response.points[0].payload == {
            "knowledge_base_id": knowledge_base_id,
            "content": "matching integration chunk",
        }
    finally:
        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)
        await client.close()


@pytest.mark.asyncio
async def test_worker_recovers_only_stale_processing_jobs() -> None:
    user_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    stale_document_id = uuid.uuid4()
    recent_document_id = uuid.uuid4()
    stale_job_id = uuid.uuid4()
    recent_job_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with AsyncSessionFactory() as session:
        try:
            await session.execute(
                text("INSERT INTO users (id, email) VALUES (:id, :email)"),
                {"id": user_id, "email": f"worker-{user_id}@example.com"},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO knowledge_bases (id, user_id, name)
                    VALUES (:id, :user_id, 'Worker Recovery KB')
                    """
                ),
                {"id": knowledge_base_id, "user_id": user_id},
            )
            for document_id, filename in (
                (stale_document_id, "stale.txt"),
                (recent_document_id, "recent.txt"),
            ):
                await session.execute(
                    text(
                        """
                        INSERT INTO documents (
                            id, knowledge_base_id, filename, content_type,
                            processed, status
                        )
                        VALUES (
                            :id, :knowledge_base_id, :filename, 'text/plain',
                            false, 'processing'
                        )
                        """
                    ),
                    {
                        "id": document_id,
                        "knowledge_base_id": knowledge_base_id,
                        "filename": filename,
                    },
                )
            for job_id, document_id, started_at in (
                (stale_job_id, stale_document_id, now - timedelta(hours=1)),
                (recent_job_id, recent_document_id, now),
            ):
                await session.execute(
                    text(
                        """
                        INSERT INTO document_jobs (
                            id, document_id, status, attempts, started_at
                        )
                        VALUES (:id, :document_id, 'processing', 1, :started_at)
                        """
                    ),
                    {
                        "id": job_id,
                        "document_id": document_id,
                        "started_at": started_at,
                    },
                )
            await session.commit()

            await DocumentWorker().recover_processing_jobs()

            rows = await session.execute(
                text(
                    """
                    SELECT j.id, j.status, d.status
                    FROM document_jobs AS j
                    JOIN documents AS d ON d.id = j.document_id
                    WHERE j.id IN (:stale_job_id, :recent_job_id)
                    """
                ),
                {
                    "stale_job_id": stale_job_id,
                    "recent_job_id": recent_job_id,
                },
            )
            statuses = {row[0]: (row[1], row[2]) for row in rows}
            assert statuses[stale_job_id] == ("pending", "pending")
            assert statuses[recent_job_id] == ("processing", "processing")
        finally:
            await session.rollback()
            await session.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": user_id},
            )
            await session.commit()
