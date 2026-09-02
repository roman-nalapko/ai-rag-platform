import uuid

from app.rag.fusion import reciprocal_rank_fusion
from app.services.search import SearchMatch


def make_match(chunk_id: uuid.UUID, content: str, score: float = 1.0) -> SearchMatch:
    return SearchMatch(
        document_id=uuid.uuid4(),
        chunk_id=chunk_id,
        chunk_index=0,
        filename="doc.txt",
        content=content,
        score=score,
    )


def test_reciprocal_rank_fusion_empty() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_reciprocal_rank_fusion_merges_and_scores() -> None:
    id_a = uuid.uuid4()
    id_b = uuid.uuid4()
    id_c = uuid.uuid4()

    match_a = make_match(id_a, "Chunk A")
    match_b = make_match(id_b, "Chunk B")
    match_c = make_match(id_c, "Chunk C")

    # List 1: [A, B]
    # List 2: [B, C]
    list1 = [match_a, match_b]
    list2 = [match_b, match_c]

    fused = reciprocal_rank_fusion([list1, list2], k=60)

    # Chunk B is present in both lists (rank 2 in list1, rank 1 in list2)
    # Score B = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.016129 + 0.016393 = 0.03252
    # Score A = 1/(60+1) = 1/61 = 0.01639
    # Score C = 1/(60+2) = 1/62 = 0.01613
    assert len(fused) == 3
    assert fused[0].chunk_id == id_b
    assert fused[1].chunk_id == id_a
    assert fused[2].chunk_id == id_c


def test_reciprocal_rank_fusion_applies_limit() -> None:
    id_a = uuid.uuid4()
    id_b = uuid.uuid4()

    list1 = [make_match(id_a, "A"), make_match(id_b, "B")]
    fused = reciprocal_rank_fusion([list1], limit=1)

    assert len(fused) == 1
    assert fused[0].chunk_id == id_a
