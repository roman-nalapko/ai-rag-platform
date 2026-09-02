import uuid
from collections import defaultdict
from collections.abc import Sequence


def reciprocal_rank_fusion[T](
    ranked_lists: Sequence[Sequence[T]],
    k: int = 60,
    limit: int | None = None,
) -> list[T]:
    """Fuse multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    Formula: RRF_score(d) = sum(1 / (k + rank_i(d)))
    """
    if not ranked_lists:
        return []

    scores: dict[uuid.UUID, float] = defaultdict(float)
    match_by_id: dict[uuid.UUID, T] = {}

    for ranked_list in ranked_lists:
        for rank, match in enumerate(ranked_list, start=1):
            chunk_id = getattr(match, "chunk_id", None)
            if chunk_id is None:
                continue
            scores[chunk_id] += 1.0 / (k + rank)
            if chunk_id not in match_by_id:
                match_by_id[chunk_id] = match

    sorted_chunk_ids = sorted(
        scores.keys(),
        key=lambda cid: scores[cid],
        reverse=True,
    )

    if limit is not None:
        sorted_chunk_ids = sorted_chunk_ids[:limit]

    return [match_by_id[cid] for cid in sorted_chunk_ids]
