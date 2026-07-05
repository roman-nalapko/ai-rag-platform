import logging
from collections.abc import AsyncIterator, Sequence
from functools import lru_cache
from time import perf_counter

from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import settings
from app.core.logging import elapsed_ms

logger = logging.getLogger(__name__)


class LMStudioClientError(RuntimeError):
    """Raised when LM Studio cannot complete a local inference request."""


class LMStudioClient:
    def __init__(
        self,
        *,
        base_url: str = settings.LM_STUDIO_BASE_URL,
        api_key: str = settings.LM_STUDIO_API_KEY,
        chat_model: str = settings.LM_STUDIO_CHAT_MODEL,
        embedding_model: str = settings.LM_STUDIO_EMBEDDING_MODEL,
        timeout_seconds: float = settings.LM_STUDIO_TIMEOUT_SECONDS,
        max_tokens: int = settings.LM_STUDIO_MAX_TOKENS,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._max_tokens = max_tokens
        self._client = client or AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Text for embedding must not be empty")

        started_at = perf_counter()
        try:
            response = await self._client.embeddings.create(
                model=self._embedding_model,
                input=text,
            )
        except OpenAIError as error:
            logger.warning(
                "embedding_failed",
                extra={
                    "operation": "embedding",
                    "outcome": "failed",
                    "duration_ms": elapsed_ms(started_at),
                },
            )
            raise LMStudioClientError(
                "LM Studio embedding request failed"
            ) from error

        if not response.data:
            logger.warning(
                "embedding_failed",
                extra={
                    "operation": "embedding",
                    "outcome": "empty_response",
                    "duration_ms": elapsed_ms(started_at),
                },
            )
            raise LMStudioClientError("LM Studio returned no embedding data")

        embedding = list(response.data[0].embedding)
        logger.info(
            "embedding_completed",
            extra={
                "operation": "embedding",
                "outcome": "completed",
                "duration_ms": elapsed_ms(started_at),
                "embedding_dimensions": len(embedding),
            },
        )
        return embedding

    async def chat_completion(
        self,
        prompt: str,
        context: str | None = None,
        history: Sequence[ChatCompletionMessageParam] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        messages = self._build_chat_messages(
            prompt=prompt,
            context=context,
            history=history,
            system_prompt=system_prompt,
        )

        started_at = perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._chat_model,
                messages=messages,
                max_tokens=self._max_tokens,
            )
        except OpenAIError as error:
            logger.warning(
                "lm_generation_failed",
                extra={
                    "operation": "chat_completion",
                    "outcome": "failed",
                    "duration_ms": elapsed_ms(started_at),
                },
            )
            raise LMStudioClientError(
                "LM Studio chat completion request failed"
            ) from error

        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            logger.warning(
                "lm_generation_failed",
                extra={
                    "operation": "chat_completion",
                    "outcome": "empty_response",
                    "duration_ms": elapsed_ms(started_at),
                },
            )
            raise LMStudioClientError("LM Studio returned an empty chat completion")

        logger.info(
            "lm_generation_completed",
            extra={
                "operation": "chat_completion",
                "outcome": "completed",
                "duration_ms": elapsed_ms(started_at),
            },
        )
        return content.strip()

    async def stream_chat_completion(
        self,
        prompt: str,
        context: str | None = None,
        history: Sequence[ChatCompletionMessageParam] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        messages = self._build_chat_messages(
            prompt=prompt,
            context=context,
            history=history,
            system_prompt=system_prompt,
        )

        started_at = perf_counter()
        try:
            stream = await self._client.chat.completions.create(
                model=self._chat_model,
                messages=messages,
                stream=True,
                max_tokens=self._max_tokens,
            )
        except OpenAIError as error:
            logger.warning(
                "lm_generation_failed",
                extra={
                    "operation": "chat_completion_stream",
                    "outcome": "failed_to_start",
                    "duration_ms": elapsed_ms(started_at),
                },
            )
            raise LMStudioClientError(
                "LM Studio streaming request failed"
            ) from error

        async def iterate_tokens() -> AsyncIterator[str]:
            received_content = False
            outcome = "interrupted"
            try:
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    content = chunk.choices[0].delta.content
                    if content:
                        received_content = True
                        yield content
                if not received_content:
                    outcome = "empty_response"
                    raise LMStudioClientError(
                        "LM Studio returned an empty streaming completion"
                    )
                outcome = "completed"
            except OpenAIError as error:
                outcome = "failed"
                raise LMStudioClientError(
                    "LM Studio streaming response failed"
                ) from error
            finally:
                try:
                    await stream.close()
                finally:
                    log_method = (
                        logger.info if outcome == "completed" else logger.warning
                    )
                    log_method(
                        (
                            "lm_generation_completed"
                            if outcome == "completed"
                            else "lm_generation_failed"
                        ),
                        extra={
                            "operation": "chat_completion_stream",
                            "outcome": outcome,
                            "duration_ms": elapsed_ms(started_at),
                        },
                    )

        return iterate_tokens()

    @staticmethod
    def _build_chat_messages(
        prompt: str,
        context: str | None,
        history: Sequence[ChatCompletionMessageParam] | None,
        system_prompt: str | None,
    ) -> list[ChatCompletionMessageParam]:
        if not prompt.strip():
            raise ValueError("Prompt must not be empty")

        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        elif context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Answer using the supplied context when it is relevant.\n\n"
                        f"Context:\n{context}"
                    ),
                }
            )
        if history:
            messages.extend(history)

        user_content = prompt
        if system_prompt and context:
            user_content = f"Context:\n{context}\n\nQuestion:\n{prompt}"
        messages.append({"role": "user", "content": user_content})
        return messages

    async def close(self) -> None:
        await self._client.close()


@lru_cache(maxsize=1)
def get_lm_studio_client() -> LMStudioClient:
    return LMStudioClient()


async def close_lm_studio_client() -> None:
    if get_lm_studio_client.cache_info().currsize == 0:
        return

    client = get_lm_studio_client()
    await client.close()
    get_lm_studio_client.cache_clear()
