from jawafdehi_agentspan.evidence.contracts import TraceabilityEntry
from jawafdehi_agentspan.evidence.finalizer import compose_final_draft


def test_compose_final_draft_requires_all_sections_and_traceability() -> None:
    sections = {
        "metadata": "## Case Metadata\n...",
        "entities": "## Entities\n...",
        "description": "## Description\n...",
        "key_allegations": "## Key Allegations\n...",
        "timeline": "## Timeline\n...",
        "evidence": "## Evidence / Sources\n...",
        "tags": "## Tags\n...",
        "missing_details": "## Missing Details\nnot available from sources",
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


def test_compose_final_draft_missing_section_returns_invalid_report() -> None:
    sections = {
        "metadata": "## Case Metadata\n...",
        "entities": "## Entities\n...",
        "description": "## Description\n...",
        "key_allegations": "## Key Allegations\n...",
        "timeline": "## Timeline\n...",
        "evidence": "## Evidence / Sources\n...",
        "tags": "## Tags\n...",
        "missing_details": "## Missing Details\nnot available from sources",
        "short_description": "सारांश",
    }
    sections.pop("timeline")
    traceability = [
        TraceabilityEntry(
            claim_text="Case description",
            section="description",
            source_refs=[{"source_id": "s1", "chunk_id": "s1#0001"}],
        )
    ]

    result = compose_final_draft(sections, traceability)

    assert result.validation.is_valid is False
    assert "timeline" in result.validation.missing_sections
    assert "missing required sections" in result.validation.errors


def test_compose_final_draft_unmapped_claim_returns_invalid_report() -> None:
    sections = {
        "metadata": "## Case Metadata\n...",
        "entities": "## Entities\n...",
        "description": "## Description\n...",
        "key_allegations": "## Key Allegations\n...",
        "timeline": "## Timeline\n...",
        "evidence": "## Evidence / Sources\n...",
        "tags": "## Tags\n...",
        "missing_details": "## Missing Details\nnot available from sources",
        "short_description": "सारांश",
    }
    traceability = [
        TraceabilityEntry(
            claim_text="Unmapped assertion",
            section="description",
            source_refs=[],
        )
    ]

    result = compose_final_draft(sections, traceability)

    assert result.validation.is_valid is False
    assert result.validation.unmapped_claims == ["Unmapped assertion"]
    assert "unmapped claims found" in result.validation.errors


def test_compose_final_draft_reports_all_invalid_conditions() -> None:
    sections = {
        "metadata": "## Case Metadata\n...",
        "entities": "## Entities\n...",
        "description": "## Description\n...",
        "key_allegations": "## Key Allegations\n...",
        "timeline": "## Timeline\n...",
        "evidence": "## Evidence / Sources\n...",
        "tags": "## Tags\n...",
        "missing_details": "## Missing Details\nnot available from sources",
        "short_description": "सारांश",
    }
    sections.pop("evidence")
    traceability = [
        TraceabilityEntry(
            claim_text="Unmapped assertion",
            section="description",
            source_refs=[],
        )
    ]

    result = compose_final_draft(sections, traceability)

    assert result.validation.is_valid is False
    assert "evidence" in result.validation.missing_sections
    assert result.validation.unmapped_claims == ["Unmapped assertion"]
    assert "missing required sections" in result.validation.errors
    assert "unmapped claims found" in result.validation.errors
