from jawafdehi_agentspan.evidence.context_selector import select_context_for_section
from jawafdehi_agentspan.evidence.contracts import ClaimCandidate, SourceChunk


def test_selector_prioritizes_amount_and_dates_for_timeline():
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
            claim_type="date",
            value="2026-04-03",
            confidence=0.9,
            source_refs=[{"source_id": "s", "chunk_id": "s#0001"}],
        ),
    ]
    selected = select_context_for_section("timeline", chunks, claims, max_chunks=2)
    assert selected.claims[0].claim_type in {"date", "event"}
    assert len(selected.chunks) <= 2
