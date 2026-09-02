from types import SimpleNamespace
from typing import Any, cast

from openai import AsyncOpenAI

from app.llm.lm_studio_client import LMStudioClient


class FakeChatCompletions:
    def __init__(self, content: str = "answer") -> None:
        self.request: dict[str, Any] | None = None
        self.content = content

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeEmbeddings:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        inputs = kwargs.get("input", [])
        if isinstance(inputs, str):
            inputs = [inputs]
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=i, embedding=[0.1 * (i + 1), 0.2 * (i + 1)])
                for i in range(len(inputs))
            ]
        )


class FakeStream:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.closed = False

    def __aiter__(self):  # type: ignore[no-untyped-def]
        async def iterate():  # type: ignore[no-untyped-def]
            for content in self.contents:
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
                )

        return iterate()

    async def close(self) -> None:
        self.closed = True


class FakeStreamingCompletions:
    def __init__(self, stream: FakeStream) -> None:
        self.stream = stream
        self.request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> FakeStream:
        self.request = kwargs
        return self.stream


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
    assert "<turn|>" in completions.request["stop"]


async def test_chat_completion_removes_model_control_markers() -> None:
    completions = FakeChatCompletions(
        content="Grounded answer.<turn|><|channel>thought"
    )
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    client = LMStudioClient(
        chat_model="test-chat-model",
        embedding_model="test-embedding-model",
        client=cast(AsyncOpenAI, fake_client),
    )
    answer = await client.chat_completion("question")

    assert answer == "Grounded answer."


async def test_stream_completion_filters_marker_split_across_chunks() -> None:
    fake_stream = FakeStream(["Grounded answer.<tu", "rn|><|channel>thought"])
    completions = FakeStreamingCompletions(fake_stream)
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    client = LMStudioClient(
        chat_model="test-chat-model",
        embedding_model="test-embedding-model",
        client=cast(AsyncOpenAI, fake_client),
    )

    token_stream = await client.stream_chat_completion("question")
    answer = "".join([token async for token in token_stream])

    assert answer == "Grounded answer."
    assert fake_stream.closed is True
    assert completions.request is not None
    assert "<|channel>" in completions.request["stop"]


async def test_embed_texts_batch_request() -> None:
    embeddings_mock = FakeEmbeddings()
    fake_client = SimpleNamespace(
        embeddings=embeddings_mock,
    )
    client = LMStudioClient(
        chat_model="test-chat-model",
        embedding_model="test-embedding-model",
        client=cast(AsyncOpenAI, fake_client),
    )

    result = await client.embed_texts(["first chunk", "second chunk"])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2]
    assert result[1] == [0.2, 0.4]
    assert embeddings_mock.request is not None
    assert embeddings_mock.request["input"] == ["first chunk", "second chunk"]


async def test_embed_text_single_request() -> None:
    embeddings_mock = FakeEmbeddings()
    fake_client = SimpleNamespace(
        embeddings=embeddings_mock,
    )
    client = LMStudioClient(
        chat_model="test-chat-model",
        embedding_model="test-embedding-model",
        client=cast(AsyncOpenAI, fake_client),
    )

    result = await client.embed_text("single chunk")

    assert result == [0.1, 0.2]
    assert embeddings_mock.request is not None
    assert embeddings_mock.request["input"] == ["single chunk"]
