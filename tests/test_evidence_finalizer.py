from jawafdehi_agentspan.evidence.contracts import TraceabilityEntry
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
        "short_description": "सारांश",
    }
    traceability = [
        TraceabilityEntry(
            claim_text="Case description",
            section="description",
            source_refs=[{"source_id": "s1", "chunk_id": "s1#0001"}],
        )
    ]

    result = compose_final_draft(sections, traceability)

    assert result.validation.is_valid is True
    assert "## Description" in result.draft_markdown
    assert result.short_description == "सारांश"
