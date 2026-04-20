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
    status: Literal["existing", "downloaded", "converted", "missing"]


class SourceChunk(BaseModel):
    chunk_id: str
    source_id: str
    content: str


class ClaimCandidate(BaseModel):
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
    confidence: float = Field(ge=0.0, le=1.0)
    source_refs: list[dict[str, str]] = Field(default_factory=list)


class TraceabilityEntry(BaseModel):
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


class ValidationReport(BaseModel):
    is_valid: bool
    missing_sections: list[str] = Field(default_factory=list)
    unmapped_claims: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
