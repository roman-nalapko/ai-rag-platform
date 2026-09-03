import logging
from collections.abc import AsyncIterator, Sequence
from functools import lru_cache
from time import perf_counter

from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import settings
from app.core.logging import elapsed_ms

logger = logging.getLogger(__name__)

MODEL_CONTROL_MARKERS = (
    "<turn|>",
    "<|channel>",
    "<|end|>",
    "<|assistant|>",
)


class LMStudioClientError(RuntimeError):
    """Raised when the LLM provider cannot complete an inference request."""


class LMStudioClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        timeout_seconds: float = settings.LM_STUDIO_TIMEOUT_SECONDS,
        max_tokens: int = settings.LM_STUDIO_MAX_TOKENS,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._chat_model = chat_model or settings.llm_chat_model
        self._embedding_model = embedding_model or settings.llm_embedding_model
        self._max_tokens = max_tokens
        self._client = client or AsyncOpenAI(
            base_url=base_url or settings.llm_base_url,
            api_key=api_key or settings.llm_api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned_texts = [text.strip() for text in texts]
        if any(not text for text in cleaned_texts):
            raise ValueError("All texts for embedding must be non-empty")

        started_at = perf_counter()
        batch_size = 64
        all_embeddings: list[list[float]] = []

        try:
            for start_idx in range(0, len(cleaned_texts), batch_size):
                batch = list(cleaned_texts[start_idx : start_idx + batch_size])
                response = await self._client.embeddings.create(
                    model=self._embedding_model,
                    input=batch,
                )

                if not response.data or len(response.data) != len(batch):
                    logger.warning(
                        "embedding_failed",
                        extra={
                            "operation": "embedding_batch",
                            "outcome": "incomplete_response",
                            "count": len(batch),
                            "received": len(response.data) if response.data else 0,
                            "duration_ms": elapsed_ms(started_at),
                        },
                    )
                    raise LMStudioClientError(
                        "LM Studio returned incomplete embedding data"
                    )

                sorted_data = sorted(response.data, key=lambda item: item.index)
                all_embeddings.extend([list(item.embedding) for item in sorted_data])
        except OpenAIError as error:
            logger.warning(
                "embedding_failed",
                extra={
                    "operation": "embedding_batch",
                    "outcome": "failed",
                    "count": len(texts),
                    "duration_ms": elapsed_ms(started_at),
                },
            )
            raise LMStudioClientError("LM Studio embedding request failed") from error

        logger.info(
            "embedding_completed",
            extra={
                "operation": "embedding_batch",
                "outcome": "completed",
                "count": len(all_embeddings),
                "duration_ms": elapsed_ms(started_at),
                "embedding_dimensions": (
                    len(all_embeddings[0]) if all_embeddings else 0
                ),
            },
        )
        return all_embeddings

    async def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Text for embedding must not be empty")

        embeddings = await self.embed_texts([text])
        return embeddings[0]

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
                stop=list(MODEL_CONTROL_MARKERS),
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
        if content:
            content = self._strip_model_control_markers(content)
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
                stop=list(MODEL_CONTROL_MARKERS),
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
            raise LMStudioClientError("LM Studio streaming request failed") from error

        async def iterate_tokens() -> AsyncIterator[str]:
            received_content = False
            outcome = "interrupted"
            pending = ""
            max_marker_length = max(map(len, MODEL_CONTROL_MARKERS))
            try:
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    content = chunk.choices[0].delta.content
                    if content:
                        pending += content
                        marker_index = self._first_control_marker_index(pending)
                        if marker_index is not None:
                            safe_content = pending[:marker_index]
                            if safe_content:
                                received_content = True
                                yield safe_content
                            pending = ""
                            break

                        safe_length = len(pending) - max_marker_length + 1
                        if safe_length > 0:
                            safe_content = pending[:safe_length]
                            pending = pending[safe_length:]
                            received_content = True
                            yield safe_content
                if pending:
                    received_content = True
                    yield pending
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
    def _first_control_marker_index(content: str) -> int | None:
        indexes = [
            index
            for marker in MODEL_CONTROL_MARKERS
            if (index := content.find(marker)) >= 0
        ]
        return min(indexes) if indexes else None

    @classmethod
    def _strip_model_control_markers(cls, content: str) -> str:
        marker_index = cls._first_control_marker_index(content)
        if marker_index is not None:
            content = content[:marker_index]
        return content.strip()

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
