from jawafdehi_agentspan.evidence.contracts import (
    ClaimCandidate,
    SourceChunk,
    SourceRegistryItem,
    TraceabilityEntry,
    ValidationReport,
)


def test_evidence_contract_models():
    registry = SourceRegistryItem(
        source_id='src-1',
        source_type='case_details',
        status='existing',
    )
    chunk = SourceChunk(
        chunk_id='chunk-1',
        source_id=registry.source_id,
        content='Sample description text',
    )
    claim = ClaimCandidate(
        claim_type='other',
        confidence=0.75,
        source_refs=[{'chunk_id': chunk.chunk_id}],
    )
    trace = TraceabilityEntry(section='description')
    report = ValidationReport(is_valid=True)

    assert claim.source_refs[0]['chunk_id'] == chunk.chunk_id
    assert trace.section == 'description'
    assert report.is_valid is True