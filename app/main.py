import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.auth import _demo_router as auth_demo_router
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.metrics import router as metrics_router
from app.api.qa import router as qa_router
from app.api.search import router as search_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.db.session import dispose_database_engine
from app.llm.lm_studio_client import close_lm_studio_client
from app.rag.vector_store import close_vector_store
from app.services.document_worker import DocumentWorker

configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    stop_worker = asyncio.Event()
    worker_task: asyncio.Task[None] | None = None
    if settings.DOCUMENT_WORKER_ENABLED:
        worker_task = asyncio.create_task(
            DocumentWorker().run_forever(stop_worker),
            name="document-worker",
        )
    try:
        yield
    finally:
        if worker_task is not None:
            stop_worker.set()
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        await close_vector_store()
        await close_lm_studio_client()
        await dispose_database_engine()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
if settings.DEMO_MODE_ENABLED:
    app.mount("/demo", StaticFiles(directory="app/web", html=True), name="demo")


app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(auth_router)
app.include_router(auth_demo_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(qa_router)
app.include_router(users_router)
app.include_router(knowledge_bases_router)
app.include_router(conversations_router)
