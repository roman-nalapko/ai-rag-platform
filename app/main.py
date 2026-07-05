from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.qa import router as qa_router
from app.api.search import router as search_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.db.session import dispose_database_engine
from app.llm.lm_studio_client import close_lm_studio_client
from app.rag.vector_store import close_vector_store

configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_vector_store()
        await close_lm_studio_client()
        await dispose_database_engine()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)


app.include_router(health_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(qa_router)
app.include_router(users_router)
app.include_router(knowledge_bases_router)
app.include_router(conversations_router)
