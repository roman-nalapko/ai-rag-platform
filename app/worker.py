import asyncio

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import dispose_database_engine
from app.llm.lm_studio_client import close_lm_studio_client
from app.rag.vector_store import close_vector_store
from app.services.document_worker import DocumentWorker


async def main() -> None:
    configure_logging(settings.LOG_LEVEL)
    stop_event = asyncio.Event()
    try:
        await DocumentWorker().run_forever(stop_event)
    finally:
        await close_vector_store()
        await close_lm_studio_client()
        await dispose_database_engine()


if __name__ == "__main__":
    asyncio.run(main())
