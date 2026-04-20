from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TraceabilityEntry(BaseModel):
    claim_text: str
    section: Literal[
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
    source_refs: list[dict[str, str]]


class ValidationReport(BaseModel):
    is_valid: bool
    missing_sections: list[str]
    unmapped_claims: list[str]
    errors: list[str]
