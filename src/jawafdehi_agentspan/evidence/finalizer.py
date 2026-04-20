from __future__ import annotations

from dataclasses import dataclass

from jawafdehi_agentspan.evidence.contracts import (
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
        section
        for section in _REQUIRED_SECTIONS
        if not sections.get(section, "").strip()
    ]
    unmapped_claims = [
        entry.claim_text for entry in traceability_entries if not entry.source_refs
    ]

    errors: list[str] = []
    if missing_sections:
        errors.append("missing required sections")
    if unmapped_claims:
        errors.append("unmapped claims found")

    validation = ValidationReport(
        is_valid=not errors,
        missing_sections=missing_sections,
        unmapped_claims=unmapped_claims,
        errors=errors,
    )

    ordered_section_names = [
        "metadata",
        "entities",
        "description",
        "key_allegations",
        "timeline",
        "evidence",
        "tags",
        "missing_details",
    ]
    ordered_sections: list[str] = []
    for section in ordered_section_names:
        heading = " ".join(part.capitalize() for part in section.split("_"))
        body = sections.get(section, "").strip()
        ordered_sections.append(f"## {heading}\n{body}".rstrip())

    return FinalizationResult(
        draft_markdown="\n\n".join(ordered_sections).strip(),
        short_description=sections["short_description"].strip(),
        validation=validation,
    )
