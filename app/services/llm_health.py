from dataclasses import dataclass

from app.llm.lm_studio_client import LMStudioClient


@dataclass(frozen=True, slots=True)
class LLMHealthResult:
    status: str
    provider: str
    embedding_dimensions: int


class LLMHealthService:
    def __init__(self, client: LMStudioClient) -> None:
        self._client = client

    async def check(self) -> LLMHealthResult:
        embedding = await self._client.embed_text("health check")
        return LLMHealthResult(
            status="ok",
            provider="lm-studio",
            embedding_dimensions=len(embedding),
        )
