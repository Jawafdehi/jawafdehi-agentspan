from __future__ import annotations

from dataclasses import dataclass

from jawafdehi_agentspan.evidence.contracts import ClaimCandidate, SourceChunk


@dataclass
class SelectedContext:
    chunks: list[SourceChunk]
    claims: list[ClaimCandidate]


_SECTION_PRIORITY = {
    "metadata": ("date", "amount", "legal_ref"),
    "entities": ("accused_name", "related_party", "location"),
    "description": ("amount", "legal_ref", "event", "other"),
    "key_allegations": ("amount", "legal_ref", "event"),
    "timeline": ("date", "event"),
    "evidence": ("other",),
    "tags": ("other",),
    "missing_details": ("other",),
    "short_description": ("amount", "event", "legal_ref"),
}


def select_context_for_section(
    section: str,
    chunks: list[SourceChunk],
    claims: list[ClaimCandidate],
    *,
    max_chunks: int = 10,
) -> SelectedContext:
    if max_chunks <= 0:
        raise ValueError("max_chunks must be positive")

    wanted = _SECTION_PRIORITY.get(section, ("other",))
    priority_index = {claim_type: idx for idx, claim_type in enumerate(wanted)}
    prioritized_claims = sorted(
        (claim for claim in claims if claim.claim_type in priority_index),
        key=lambda claim: (
            priority_index[claim.claim_type],
            claim.value,
            claim.claim_id,
        ),
    )
    fallback_claims = sorted(
        claims,
        key=lambda claim: (claim.claim_type, claim.value, claim.claim_id),
    )
    selected_claims = prioritized_claims or fallback_claims

    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    selected_chunks: list[SourceChunk] = []
    seen_chunk_ids: set[str] = set()
    for claim in selected_claims:
        for ref in claim.source_refs:
            chunk_id = ref.get("chunk_id")
            if not chunk_id or chunk_id in seen_chunk_ids:
                continue
            chunk = chunk_by_id.get(chunk_id)
            if chunk is None:
                continue
            selected_chunks.append(chunk)
            seen_chunk_ids.add(chunk_id)
    if not selected_chunks:
        selected_chunks = chunks[:max_chunks]

    return SelectedContext(
        chunks=selected_chunks[:max_chunks],
        claims=selected_claims,
    )
