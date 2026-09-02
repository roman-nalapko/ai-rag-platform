from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from openai.types.chat import ChatCompletionMessageParam


class LLMClient(Protocol):
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_text(self, text: str) -> list[float]: ...

    async def chat_completion(
        self,
        prompt: str,
        context: str | None = None,
        history: Sequence[ChatCompletionMessageParam] | None = None,
        system_prompt: str | None = None,
    ) -> str: ...

    async def stream_chat_completion(
        self,
        prompt: str,
        context: str | None = None,
        history: Sequence[ChatCompletionMessageParam] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]: ...

    async def close(self) -> None: ...


from app.llm.lm_studio_client import (  # noqa: E402
    LMStudioClient,
    close_lm_studio_client,
    get_lm_studio_client,
)

get_llm_client = get_lm_studio_client
close_llm_client = close_lm_studio_client
OpenAICompatibleClient = LMStudioClient
