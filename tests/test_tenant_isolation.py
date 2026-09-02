import uuid
from types import SimpleNamespace

import pytest

from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.services.conversation import (
    ConversationKnowledgeBaseNotFoundError,
    ConversationService,
)
from app.services.document import (
    DocumentAlreadyProcessingError,
    DocumentNotFoundError,
    DocumentService,
)
from app.services.knowledge_base import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
)
from app.services.search import SearchKnowledgeBaseNotFoundError, SearchService


class FakeKnowledgeBaseSession:
    async def get(self, model: object, identifier: uuid.UUID) -> object | None:
        return None


class FakeSearchSession:
    def __init__(self, knowledge_base: object | None) -> None:
        self.knowledge_base = knowledge_base
        self.rolled_back = False

    async def get(self, model: object, identifier: uuid.UUID) -> object | None:
        if model is KnowledgeBase:
            return self.knowledge_base
        return None

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeDocumentSession:
    def __init__(self, document: object, knowledge_base: object) -> None:
        self.document = document
        self.knowledge_base = knowledge_base

    async def get(self, model: object, identifier: uuid.UUID) -> object | None:
        if model is Document:
            return self.document
        if model is KnowledgeBase:
            return self.knowledge_base
        return None


class FakeConversationSession:
    def __init__(self, knowledge_base: object) -> None:
        self.knowledge_base = knowledge_base

    async def get(self, model: object, identifier: uuid.UUID) -> object | None:
        if model is KnowledgeBase:
            return self.knowledge_base
        return None


@pytest.mark.asyncio
async def test_knowledge_base_create_rejects_user_id_mismatch() -> None:
    service = KnowledgeBaseService(FakeKnowledgeBaseSession())  # type: ignore[arg-type]

    with pytest.raises(KnowledgeBaseAccessDeniedError):
        await service.create(
            user_id=uuid.uuid4(),
            name="Engineering",
            description=None,
            current_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_search_rejects_cross_tenant_knowledge_base() -> None:
    current_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    knowledge_base = SimpleNamespace(id=uuid.uuid4(), user_id=other_user_id)
    session = FakeSearchSession(knowledge_base)
    service = SearchService(
        session=session,  # type: ignore[arg-type]
        embedding_client=SimpleNamespace(),  # type: ignore[arg-type]
        vector_store=SimpleNamespace(),  # type: ignore[arg-type]
        reranker=SimpleNamespace(),  # type: ignore[arg-type]
    )

    with pytest.raises(SearchKnowledgeBaseNotFoundError):
        await service.search(
            query="dependencies",
            limit=5,
            knowledge_base_id=knowledge_base.id,
            current_user_id=current_user_id,
        )

    assert session.rolled_back is False


@pytest.mark.asyncio
async def test_document_get_rejects_cross_tenant_document() -> None:
    document = SimpleNamespace(id=uuid.uuid4(), knowledge_base_id=uuid.uuid4())
    knowledge_base = SimpleNamespace(
        id=document.knowledge_base_id, user_id=uuid.uuid4()
    )
    service = DocumentService(
        FakeDocumentSession(document, knowledge_base),  # type: ignore[arg-type]
    )

    with pytest.raises(DocumentNotFoundError):
        await service.get(document.id, current_user_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_conversation_create_rejects_cross_tenant_knowledge_base() -> None:
    knowledge_base = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    service = ConversationService(
        FakeConversationSession(knowledge_base),  # type: ignore[arg-type]
    )

    with pytest.raises(ConversationKnowledgeBaseNotFoundError):
        await service.create(
            knowledge_base_id=knowledge_base.id,
            title="Wrong tenant",
            current_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_document_list_rejects_cross_tenant_knowledge_base() -> None:
    knowledge_base = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    service = DocumentService(
        FakeDocumentSession(SimpleNamespace(), knowledge_base),  # type: ignore[arg-type]
    )

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.list_for_knowledge_base(
            knowledge_base_id=knowledge_base.id,
            current_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_conversation_list_rejects_cross_tenant_knowledge_base() -> None:
    knowledge_base = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    service = ConversationService(
        FakeConversationSession(knowledge_base),  # type: ignore[arg-type]
    )

    with pytest.raises(ConversationKnowledgeBaseNotFoundError):
        await service.list_for_knowledge_base(
            knowledge_base_id=knowledge_base.id,
            current_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_knowledge_base_get_rejects_cross_tenant_knowledge_base() -> None:
    knowledge_base = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    class FakeSession:
        async def get(self, model: object, identifier: uuid.UUID) -> object | None:
            if model is KnowledgeBase:
                return knowledge_base
            return None

    service = KnowledgeBaseService(FakeSession())  # type: ignore[arg-type]

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.get(knowledge_base.id, current_user_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_knowledge_base_delete_rejects_cross_tenant_knowledge_base() -> None:
    knowledge_base = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    class FakeSession:
        async def get(self, model: object, identifier: uuid.UUID) -> object | None:
            if model is KnowledgeBase:
                return knowledge_base
            return None

    service = KnowledgeBaseService(FakeSession())  # type: ignore[arg-type]

    with pytest.raises(KnowledgeBaseNotFoundError):
        await service.delete(knowledge_base.id, current_user_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_search_hybrid_rejects_cross_tenant_knowledge_base() -> None:
    current_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    knowledge_base = SimpleNamespace(id=uuid.uuid4(), user_id=other_user_id)
    session = FakeSearchSession(knowledge_base)
    service = SearchService(
        session=session,  # type: ignore[arg-type]
        embedding_client=SimpleNamespace(),  # type: ignore[arg-type]
        vector_store=SimpleNamespace(),  # type: ignore[arg-type]
        reranker=SimpleNamespace(),  # type: ignore[arg-type]
    )

    with pytest.raises(SearchKnowledgeBaseNotFoundError):
        await service.search_hybrid(
            query="dependencies",
            limit=5,
            knowledge_base_id=knowledge_base.id,
            current_user_id=current_user_id,
        )


@pytest.mark.asyncio
async def test_document_reindex_and_delete_reject_cross_tenant() -> None:
    document = SimpleNamespace(
        id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        status="indexed",
        filename="doc.txt",
    )
    knowledge_base = SimpleNamespace(
        id=document.knowledge_base_id, user_id=uuid.uuid4()
    )
    service = DocumentService(
        FakeDocumentSession(document, knowledge_base),  # type: ignore[arg-type]
    )

    # Reindex
    with pytest.raises(DocumentNotFoundError):
        await service.enqueue_reindex(document.id, current_user_id=uuid.uuid4())

    # Delete
    with pytest.raises(DocumentNotFoundError):
        await service.delete(document.id, current_user_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_document_reindex_rejects_duplicate_pending_job() -> None:
    user_id = uuid.uuid4()
    document = SimpleNamespace(
        id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        status="pending",
        filename="doc.txt",
    )
    knowledge_base = SimpleNamespace(
        id=document.knowledge_base_id,
        user_id=user_id,
    )
    service = DocumentService(
        FakeDocumentSession(document, knowledge_base),  # type: ignore[arg-type]
    )

    with pytest.raises(
        DocumentAlreadyProcessingError,
        match="already queued or being processed",
    ):
        await service.enqueue_reindex(document.id, current_user_id=user_id)
