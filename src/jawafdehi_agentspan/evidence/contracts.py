from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceRegistryItem(BaseModel):
    source_id: str
    source_type: Literal[
        "case_details",
        "press_release",
        "charge_sheet",
        "news",
        "court_order",
        "bolpatra",
    ]
    url: str | None = None
    raw_path: str
    markdown_path: str
    status: Literal["existing", "downloaded", "converted", "missing"]


class SourceChunk(BaseModel):
    chunk_id: str
    source_id: str
    text: str
    char_start: int
    char_end: int
    token_estimate: int


class ClaimCandidate(BaseModel):
    claim_id: str
    claim_type: Literal[
        "accused_name",
        "related_party",
        "date",
        "amount",
        "legal_ref",
        "event",
        "location",
        "other",
    ]
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_refs: list[dict[str, str]]


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
