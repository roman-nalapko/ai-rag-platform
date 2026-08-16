import os
import uuid

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionFactory

pytestmark = pytest.mark.integration


def integration_tests_enabled() -> bool:
    return os.getenv("RUN_INTEGRATION_TESTS") == "1"


@pytest.fixture(autouse=True)
def require_integration_flag() -> None:
    if not integration_tests_enabled():
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")


@pytest.mark.asyncio
async def test_postgres_migrations_and_document_chunk_persistence() -> None:
    user_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    email = f"integration-{user_id}@example.com"

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
