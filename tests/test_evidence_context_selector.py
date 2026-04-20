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
