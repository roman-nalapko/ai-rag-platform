from dataclasses import dataclass

import pytest

from app.core.config import settings
from app.rag.reranker import KeywordOverlapReranker, NoOpReranker
from app.services.search import SearchService


@dataclass(frozen=True)
class Match:
    content: str


def test_noop_reranker_preserves_existing_order() -> None:
    matches = [
        Match(content="postgres qdrant"),
        Match(content="fastapi search"),
    ]

    reranked = NoOpReranker().rerank("fastapi", matches, limit=2)

    assert reranked == matches


def test_keyword_overlap_reranker_prefers_query_terms() -> None:
    matches = [
        Match(content="postgres migrations"),
        Match(content="fastapi qdrant semantic search"),
        Match(content="docker compose"),
    ]

    reranked = KeywordOverlapReranker().rerank(
        "semantic search with qdrant",
        matches,
        limit=2,
    )

    assert reranked == [
        Match(content="fastapi qdrant semantic search"),
        Match(content="postgres migrations"),
    ]


def test_search_candidate_limit_is_unchanged_when_reranking_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RERANKING_ENABLED", False)
    monkeypatch.setattr(settings, "RERANKING_CANDIDATE_MULTIPLIER", 3)

    assert SearchService._candidate_limit(5) == 5


def test_search_candidate_limit_expands_when_reranking_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RERANKING_ENABLED", True)
    monkeypatch.setattr(settings, "RERANKING_CANDIDATE_MULTIPLIER", 3)

    assert SearchService._candidate_limit(5) == 15
    assert SearchService._candidate_limit(50) == 50
