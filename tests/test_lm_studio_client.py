from types import SimpleNamespace
from typing import Any, cast

from openai import AsyncOpenAI

from app.llm.lm_studio_client import LMStudioClient


class FakeChatCompletions:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))]
        )


async def test_chat_completion_applies_configured_token_limit() -> None:
    completions = FakeChatCompletions()
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    client = LMStudioClient(
        chat_model="test-chat-model",
        embedding_model="test-embedding-model",
        max_tokens=17,
        client=cast(AsyncOpenAI, fake_client),
    )

    answer = await client.chat_completion("question")

    assert answer == "answer"
    assert completions.request is not None
    assert completions.request["max_tokens"] == 17
