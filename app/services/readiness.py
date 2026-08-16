from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.vector_store import VectorStoreError, VectorStoreService


class ReadinessCheckError(RuntimeError):
    """Raised when a required runtime dependency is unavailable."""


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    status: str
    checks: dict[str, str]


class ReadinessService:
    def __init__(
        self,
        session: AsyncSession,
        vector_store: VectorStoreService,
    ) -> None:
        self._session = session
        self._vector_store = vector_store

    async def check(self) -> ReadinessResult:
        checks: dict[str, str] = {}
        await self._check_database()
        checks["database"] = "ok"

        await self._check_qdrant()
        checks["qdrant"] = "ok"

        return ReadinessResult(
            status="ready",
            checks=checks,
        )

    async def _check_database(self) -> None:
        try:
            await self._session.execute(text("SELECT 1"))
        except Exception as error:
            raise ReadinessCheckError("PostgreSQL is unavailable") from error

    async def _check_qdrant(self) -> None:
        try:
            await self._vector_store.ping()
        except VectorStoreError as error:
            raise ReadinessCheckError("Qdrant is unavailable") from error
