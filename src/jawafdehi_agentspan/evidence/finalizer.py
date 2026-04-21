from __future__ import annotations

import re
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
_MISSING_DATA_MARKER = "not available from sources"


@dataclass
class FinalizationResult:
    draft_markdown: str
    short_description: str
    validation: ValidationReport


def ensure_missing_data_marker(draft_markdown: str) -> str:
    section_pattern = r"(?ms)^(##\s*Missing Details\s*\n)(.*?)(?=^##\s|\Z)"
    match = re.search(section_pattern, draft_markdown)
    if match:
        existing_content = match.group(2).strip()
        if existing_content:
            return draft_markdown
        replacement = f"{match.group(1)}{_MISSING_DATA_MARKER}\n"
        return (
            draft_markdown[: match.start()]
            + replacement
            + draft_markdown[match.end() :]
        )

    trimmed = draft_markdown.rstrip()
    separator = "\n\n" if trimmed else ""
    return f"{trimmed}{separator}## Missing Details\n{_MISSING_DATA_MARKER}\n"


def compose_final_draft(
    sections: dict[str, str],
    traceability_entries: list[TraceabilityEntry],
) -> FinalizationResult:
    """Compose the final markdown draft and a validation report.

    Contract:
    - `draft_markdown` is empty only when any required section is missing
      (including blank/whitespace-only section values).
    - If required sections are present, markdown is composed even when
      traceability validation fails due to unmapped claims.
    """
    normalized_sections = dict(sections)
    if not normalized_sections.get("missing_details", "").strip():
        normalized_sections["missing_details"] = (
            f"## Missing Details\n{_MISSING_DATA_MARKER}"
        )

    missing_sections = [
        section
        for section in _REQUIRED_SECTIONS
        if not normalized_sections.get(section, "").strip()
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

    # Missing required sections is the only condition that suppresses
    # markdown composition and forces an empty draft.
    if missing_sections:
        return FinalizationResult(
            draft_markdown="",
            short_description=normalized_sections.get("short_description", "").strip(),
            validation=validation,
        )

    ordered = [
        normalized_sections["metadata"],
        normalized_sections["entities"],
        normalized_sections["description"],
        normalized_sections["key_allegations"],
        normalized_sections["timeline"],
        normalized_sections["evidence"],
        normalized_sections["tags"],
        normalized_sections["missing_details"],
    ]

    return FinalizationResult(
        draft_markdown="\n\n".join(ordered),
        short_description=normalized_sections["short_description"].strip(),
        validation=validation,
    )
