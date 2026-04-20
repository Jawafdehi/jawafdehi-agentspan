from __future__ import annotations

from dataclasses import dataclass

from jawafdehi_agentspan.evidence.contracts import (
    ClaimCandidate,
    TraceabilityEntry,
    ValidationReport,
)

_REQUIRED_SECTIONS = [
    "metadata",
    "entities",
    "description",
    "key_allegations",
    "timeline",
    "evidence",
    "tags",
    "missing_details",
]


@dataclass
class FinalizationResult:
    draft_markdown: str
    validation: ValidationReport
    short_description: str


def compose_final_draft(
    sections: dict[str, str],
    traceability_entries: list[TraceabilityEntry],
    claims: list[ClaimCandidate],
    *,
    short_description: str,
    errors: list[str] | None = None,
) -> FinalizationResult:
    missing_sections = [
        section for section in _REQUIRED_SECTIONS if not sections.get(section, "").strip()
    ]
    mapped_claims = {
        entry.claim_text.strip() for entry in traceability_entries if entry.claim_text.strip()
    }
    unmapped_claims = [
        claim.claim_id
        for claim in claims
        if claim.value.strip() and claim.value.strip() not in mapped_claims
    ]

    validation_errors = list(errors or [])
    if not short_description.strip():
        validation_errors.append("short_description is required")

    validation = ValidationReport(
        is_valid=not missing_sections and not unmapped_claims and not validation_errors,
        missing_sections=missing_sections,
        unmapped_claims=unmapped_claims,
        errors=validation_errors,
    )

    ordered_sections: list[str] = []
    for section in _REQUIRED_SECTIONS:
        heading = " ".join(part.capitalize() for part in section.split("_"))
        body = sections.get(section, "").strip()
        ordered_sections.append(f"## {heading}\n{body}".rstrip())

    return FinalizationResult(
        draft_markdown="\n\n".join(ordered_sections).strip(),
        validation=validation,
        short_description=short_description,
    )
