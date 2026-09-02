"""Unit tests for TextChunkingService."""

import pytest

from app.services.chunking import TextChunkingService


def test_empty_text_returns_empty_list() -> None:
    service = TextChunkingService(chunk_size=100, chunk_overlap=20)
    assert service.split("") == []


def test_whitespace_only_text_returns_empty_list() -> None:
    service = TextChunkingService(chunk_size=100, chunk_overlap=20)
    assert service.split("   \n\t  ") == []


def test_text_shorter_than_chunk_size_returns_single_chunk() -> None:
    service = TextChunkingService(chunk_size=100, chunk_overlap=20)
    chunks = service.split("Hello world")
    assert chunks == ["Hello world"]


def test_text_exactly_chunk_size_returns_single_chunk() -> None:
    text = "a" * 100
    service = TextChunkingService(chunk_size=100, chunk_overlap=20)
    chunks = service.split(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_overlap_creates_multiple_chunks() -> None:
    """With chunk_size=10 and overlap=5, a 20-char text should produce 3 chunks."""
    text = "abcdefghijklmnopqrst"  # 20 chars
    service = TextChunkingService(chunk_size=10, chunk_overlap=5)
    chunks = service.split(text)
    assert len(chunks) >= 2
    # Verify overlap: second chunk should start with the last 5 chars of first chunk
    assert chunks[1].startswith(chunks[0][-5:])


def test_each_chunk_does_not_exceed_chunk_size() -> None:
    long_text = " ".join(["word"] * 500)
    service = TextChunkingService(chunk_size=50, chunk_overlap=10)
    chunks = service.split(long_text)
    for chunk in chunks:
        assert len(chunk) <= 50


def test_all_content_is_preserved_without_overlap() -> None:
    """With no overlap, concatenation of chunks should equal the original text."""
    text = "a" * 300
    service = TextChunkingService(chunk_size=100, chunk_overlap=0)
    chunks = service.split(text)
    assert "".join(chunks) == text


def test_single_character_text() -> None:
    service = TextChunkingService(chunk_size=100, chunk_overlap=20)
    chunks = service.split("x")
    assert chunks == ["x"]


def test_chunk_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        TextChunkingService(chunk_size=0)


def test_chunk_overlap_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        TextChunkingService(chunk_size=100, chunk_overlap=-1)


def test_chunk_overlap_must_be_less_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        TextChunkingService(chunk_size=100, chunk_overlap=100)
