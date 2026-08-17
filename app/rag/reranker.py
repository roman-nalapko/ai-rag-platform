import re
from collections.abc import Sequence
from typing import Protocol, TypeVar

from app.core.config import settings

T = TypeVar("T")
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class Reranker(Protocol):
    def rerank(self, query: str, matches: Sequence[T], limit: int) -> list[T]:
        """Return matches in final context order."""


class NoOpReranker:
    def rerank(self, query: str, matches: Sequence[T], limit: int) -> list[T]:
        return list(matches[:limit])


class KeywordOverlapReranker:
    """Local-first reranker for demos without external model dependencies."""

    def rerank(self, query: str, matches: Sequence[T], limit: int) -> list[T]:
        query_terms = self._tokenize(query)
        if not query_terms:
            return list(matches[:limit])

        scored_matches = [
            (self._overlap_score(query_terms, str(getattr(match, "content", ""))), index, match)
            for index, match in enumerate(matches)
        ]
        scored_matches.sort(key=lambda item: (-item[0], item[1]))
        return [match for _, _, match in scored_matches[:limit]]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token.lower() for token in TOKEN_PATTERN.findall(text)}

    @classmethod
    def _overlap_score(cls, query_terms: set[str], content: str) -> float:
        content_terms = cls._tokenize(content)
        if not content_terms:
            return 0.0
        return len(query_terms & content_terms) / len(query_terms)


def get_reranker() -> Reranker:
    if settings.RERANKING_ENABLED:
        return KeywordOverlapReranker()
    return NoOpReranker()
