import pytest

from jawafdehi_agentspan.evidence.context_selector import select_context_for_section
from jawafdehi_agentspan.evidence.contracts import ClaimCandidate, SourceChunk


def test_selector_prioritizes_date_and_event_for_timeline():
    chunks = [
        SourceChunk(
            chunk_id="s#0001",
            source_id="s",
            text="मिति २०८२-०१-०१",
            char_start=0,
            char_end=20,
            token_estimate=5,
        ),
        SourceChunk(
            chunk_id="s#0002",
            source_id="s",
            text="रु 560000000",
            char_start=21,
            char_end=40,
            token_estimate=5,
        ),
        SourceChunk(
            chunk_id="s#0003",
            source_id="s",
            text="घटना सम्बन्धी विवरण",
            char_start=41,
            char_end=70,
            token_estimate=8,
        ),
    ]
    claims = [
        ClaimCandidate(
            claim_id="c1",
            claim_type="amount",
            value="560000000",
            confidence=0.9,
            source_refs=[{"source_id": "s", "chunk_id": "s#0002"}],
        ),
        ClaimCandidate(
            claim_id="c2",
            claim_type="event",
            value="घटना भएको छ",
            confidence=0.9,
            source_refs=[{"source_id": "s", "chunk_id": "s#0003"}],
        ),
        ClaimCandidate(
            claim_id="c3",
            claim_type="date",
            value="2026-04-03",
            confidence=0.9,
            source_refs=[{"source_id": "s", "chunk_id": "s#0001"}],
        ),
    ]
    selected = select_context_for_section("timeline", chunks, claims, max_chunks=2)
    assert [claim.claim_type for claim in selected.claims] == ["date", "event"]
    assert all(claim.claim_type != "amount" for claim in selected.claims)
    assert [chunk.chunk_id for chunk in selected.chunks] == ["s#0001", "s#0003"]
    assert len(selected.chunks) <= 2


def test_selector_rejects_non_positive_max_chunks() -> None:
    with pytest.raises(ValueError, match="max_chunks must be positive"):
        select_context_for_section("timeline", [], [], max_chunks=0)


def test_selector_unknown_section_falls_back_to_other_claims() -> None:
    chunks = [
        SourceChunk(
            chunk_id="s#0001",
            source_id="s",
            text="other chunk",
            char_start=0,
            char_end=10,
            token_estimate=3,
        ),
        SourceChunk(
            chunk_id="s#0002",
            source_id="s",
            text="event chunk",
            char_start=11,
            char_end=20,
            token_estimate=3,
        ),
    ]
    claims = [
        ClaimCandidate(
            claim_id="c-event",
            claim_type="event",
            value="event value",
            confidence=0.8,
            source_refs=[{"source_id": "s", "chunk_id": "s#0002"}],
        ),
        ClaimCandidate(
            claim_id="c-other",
            claim_type="other",
            value="other value",
            confidence=0.8,
            source_refs=[{"source_id": "s", "chunk_id": "s#0001"}],
        ),
    ]

    selected = select_context_for_section(
        "unknown_section",
        chunks,
        claims,
        max_chunks=5,
    )

    assert [claim.claim_id for claim in selected.claims] == ["c-other"]
    assert [chunk.chunk_id for chunk in selected.chunks] == ["s#0001"]


def test_selector_fallback_claim_order_is_deterministic() -> None:
    chunks = [
        SourceChunk(
            chunk_id="s#0001",
            source_id="s",
            text="claim a",
            char_start=0,
            char_end=10,
            token_estimate=3,
        ),
        SourceChunk(
            chunk_id="s#0002",
            source_id="s",
            text="claim b",
            char_start=11,
            char_end=20,
            token_estimate=3,
        ),
        SourceChunk(
            chunk_id="s#0003",
            source_id="s",
            text="claim c",
            char_start=21,
            char_end=30,
            token_estimate=3,
        ),
    ]
    claims = [
        ClaimCandidate(
            claim_id="c3",
            claim_type="location",
            value="kathmandu",
            confidence=0.6,
            source_refs=[{"source_id": "s", "chunk_id": "s#0003"}],
        ),
        ClaimCandidate(
            claim_id="c2",
            claim_type="amount",
            value="300",
            confidence=0.6,
            source_refs=[{"source_id": "s", "chunk_id": "s#0002"}],
        ),
        ClaimCandidate(
            claim_id="c1",
            claim_type="amount",
            value="200",
            confidence=0.6,
            source_refs=[{"source_id": "s", "chunk_id": "s#0001"}],
        ),
    ]

    selected = select_context_for_section("timeline", chunks, claims, max_chunks=5)

    assert [claim.claim_id for claim in selected.claims] == ["c1", "c2", "c3"]
    assert [chunk.chunk_id for chunk in selected.chunks] == [
        "s#0001",
        "s#0002",
        "s#0003",
    ]


def test_selector_prioritized_same_priority_ties_are_deterministic() -> None:
    chunks = [
        SourceChunk(
            chunk_id="s#0001",
            source_id="s",
            text="मिति २०८२-०१-०२",
            char_start=0,
            char_end=20,
            token_estimate=5,
        ),
        SourceChunk(
            chunk_id="s#0002",
            source_id="s",
            text="मिति २०८२-०१-०१",
            char_start=21,
            char_end=40,
            token_estimate=5,
        ),
    ]
    claims = [
        ClaimCandidate(
            claim_id="c2",
            claim_type="date",
            value="2026-04-03",
            confidence=0.9,
            source_refs=[{"source_id": "s", "chunk_id": "s#0001"}],
        ),
        ClaimCandidate(
            claim_id="c1",
            claim_type="date",
            value="2026-04-03",
            confidence=0.9,
            source_refs=[{"source_id": "s", "chunk_id": "s#0002"}],
        ),
    ]

    selected = select_context_for_section("timeline", chunks, claims, max_chunks=5)

    assert [claim.claim_id for claim in selected.claims] == ["c1", "c2"]
    assert [chunk.chunk_id for chunk in selected.chunks] == ["s#0002", "s#0001"]


def test_selector_ignores_missing_and_duplicate_chunk_refs() -> None:
    chunks = [
        SourceChunk(
            chunk_id="s#0001",
            source_id="s",
            text="chunk 1",
            char_start=0,
            char_end=10,
            token_estimate=3,
        ),
        SourceChunk(
            chunk_id="s#0002",
            source_id="s",
            text="chunk 2",
            char_start=11,
            char_end=20,
            token_estimate=3,
        ),
    ]
    claims = [
        ClaimCandidate(
            claim_id="c1",
            claim_type="other",
            value="first",
            confidence=0.6,
            source_refs=[
                {"source_id": "s", "chunk_id": "missing"},
                {"source_id": "s", "chunk_id": "s#0001"},
                {"source_id": "s", "chunk_id": "s#0001"},
            ],
        )
    ]

    selected = select_context_for_section("evidence", chunks, claims, max_chunks=2)

    assert [chunk.chunk_id for chunk in selected.chunks] == ["s#0001"]
