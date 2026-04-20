from jawafdehi_agentspan.evidence.contracts import ClaimCandidate, TraceabilityEntry
from jawafdehi_agentspan.evidence.finalizer import compose_final_draft


def test_compose_final_draft_validates_and_orders_sections() -> None:
    sections = {
        "metadata": "Case metadata",
        "entities": "- **Entity**",
        "description": "Case description",
        "key_allegations": "- Allegation",
        "timeline": "- 2026-01 घटना",
        "evidence": "Evidence details",
        "tags": "#tag",
        "missing_details": "None",
    }
    claims = [
        ClaimCandidate(
            claim_id="claim-1",
            claim_type="event",
            value="Case description",
            confidence=0.9,
            source_refs=[{"source_id": "s1", "chunk_id": "s1#0001"}],
        )
    ]
    traceability = [
        TraceabilityEntry(
            claim_text="Case description",
            section="description",
            source_refs=[{"source_id": "s1", "chunk_id": "s1#0001"}],
        )
    ]

    result = compose_final_draft(
        sections,
        traceability,
        claims,
        short_description="सारांश",
    )

    assert result.validation.is_valid is True
    assert "## Description" in result.draft_markdown
    assert result.short_description == "सारांश"
    assert result.validation.missing_sections == []
    assert result.validation.unmapped_claims == []
    assert result.validation.errors == []

    expected_order = [
        "## Metadata",
        "## Entities",
        "## Description",
        "## Key Allegations",
        "## Timeline",
        "## Evidence",
        "## Tags",
        "## Missing Details",
    ]
    indices = [result.draft_markdown.index(heading) for heading in expected_order]
    assert indices == sorted(indices)
