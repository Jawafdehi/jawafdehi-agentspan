from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
