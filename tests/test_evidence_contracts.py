from jawafdehi_agentspan.evidence.contracts import (
    ClaimCandidate,
    SourceChunk,
    SourceRegistryItem,
    TraceabilityEntry,
    ValidationReport,
)


def test_evidence_contracts_round_trip() -> None:
    registry = SourceRegistryItem(
        source_id="src-1",
        source_type="case_details",
        url="https://example.org/source/1",
        raw_path="files/raw/src-1.pdf",
        markdown_path="files/markdown/src-1.md",
        status="existing",
    )
    registry_rt = SourceRegistryItem.model_validate(registry.model_dump())

    chunk = SourceChunk(
        chunk_id="chunk-1",
        source_id=registry_rt.source_id,
        text="The incident happened on 2024-01-01 in Kathmandu.",
        char_start=0,
        char_end=52,
        token_estimate=12,
    )
    chunk_rt = SourceChunk.model_validate(chunk.model_dump())

    claim = ClaimCandidate(
        claim_id="claim-1",
        claim_type="event",
        value="Incident occurred in Kathmandu on 2024-01-01",
        confidence=0.87,
        source_refs=[
            {"source_id": registry_rt.source_id, "chunk_id": chunk_rt.chunk_id}
        ],
    )
    claim_rt = ClaimCandidate.model_validate(claim.model_dump())

    trace = TraceabilityEntry(
        claim_text=claim_rt.value,
        section="description",
        source_refs=[
            {"source_id": registry_rt.source_id, "chunk_id": chunk_rt.chunk_id}
        ],
    )
    trace_rt = TraceabilityEntry.model_validate(trace.model_dump())

    report = ValidationReport(
        is_valid=True,
        missing_sections=[],
        unmapped_claims=[],
        errors=[],
    )
    report_rt = ValidationReport.model_validate(report.model_dump())

    assert claim_rt.source_refs[0]["chunk_id"] == chunk_rt.chunk_id
    assert trace_rt.section == "description"
    assert report_rt.is_valid is True
