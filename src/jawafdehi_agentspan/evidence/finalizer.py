from __future__ import annotations

from dataclasses import dataclass

from jawafdehi_agentspan.evidence.contracts import TraceabilityEntry, ValidationReport

_REQUIRED_SECTIONS = [
    "metadata",
    "entities",
    "description",
    "key_allegations",
    "timeline",
    "evidence",
    "tags",
    "missing_details",
    "short_description",
]


@dataclass
class FinalizationResult:
    draft_markdown: str
    short_description: str
    validation: ValidationReport


def compose_final_draft(
    sections: dict[str, str],
    traceability_entries: list[TraceabilityEntry],
) -> FinalizationResult:
    missing_sections = [
        section for section in _REQUIRED_SECTIONS if not sections.get(section, "").strip()
    ]
    unmapped_claims = [
        entry.claim_text for entry in traceability_entries if not entry.source_refs
    ]
    errors: list[str] = []
    if missing_sections:
        errors.append("missing required sections")
    if unmapped_claims:
        errors.append("unmapped claims found")

    ordered = [
        sections["metadata"],
        sections["entities"],
        sections["description"],
        sections["key_allegations"],
        sections["timeline"],
        sections["evidence"],
        sections["tags"],
        sections["missing_details"],
    ]
    report = ValidationReport(
        is_valid=not errors,
        missing_sections=missing_sections,
        unmapped_claims=unmapped_claims,
        errors=errors,
    )
    return FinalizationResult(
        draft_markdown="\n\n".join(ordered),
        short_description=sections["short_description"].strip(),
        validation=report,
    )
