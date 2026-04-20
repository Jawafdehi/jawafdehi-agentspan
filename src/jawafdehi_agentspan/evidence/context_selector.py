from __future__ import annotations

from dataclasses import dataclass

from jawafdehi_agentspan.evidence.contracts import ClaimCandidate, SourceChunk


@dataclass
class SelectedContext:
    chunks: list[SourceChunk]
    claims: list[ClaimCandidate]


_SECTION_PRIORITY = {
    "metadata": {"date", "amount", "legal_ref"},
    "entities": {"accused_name", "related_party", "location"},
    "description": {"amount", "legal_ref", "event", "other"},
    "key_allegations": {"amount", "legal_ref", "event"},
    "timeline": {"date", "event"},
    "evidence": {"other"},
    "tags": {"other"},
    "missing_details": {"other"},
    "short_description": {"amount", "event", "legal_ref"},
}


def select_context_for_section(
    section: str,
    chunks: list[SourceChunk],
    claims: list[ClaimCandidate],
    *,
    max_chunks: int = 10,
) -> SelectedContext:
    wanted = _SECTION_PRIORITY.get(section, {"other"})
    prioritized_claims = [claim for claim in claims if claim.claim_type in wanted]
    selected_claims = prioritized_claims or claims

    claim_chunk_ids = {
        ref["chunk_id"]
        for claim in selected_claims
        for ref in claim.source_refs
        if "chunk_id" in ref
    }
    selected_chunks = [chunk for chunk in chunks if chunk.chunk_id in claim_chunk_ids]
    if not selected_chunks:
        selected_chunks = chunks[:max_chunks]

    return SelectedContext(
        chunks=selected_chunks[:max_chunks],
        claims=selected_claims,
    )
