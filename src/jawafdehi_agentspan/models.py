from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

CASE_NUMBER_PATTERN = r"^\d{3}-[A-Z]{2,5}-\d{4}$"
AcceptedCIAACaseNumber = Annotated[
    str,
    BeforeValidator(
        lambda value: value.strip().upper() if isinstance(value, str) else value
    ),
    StringConstraints(pattern=CASE_NUMBER_PATTERN),
]


class CIAACaseInput(BaseModel):
    case_number: AcceptedCIAACaseNumber


class WorkspaceContext(BaseModel):
    root_dir: Path
    logs_dir: Path
    data_dir: Path
    memory_file: Path


class CaseInitialization(BaseModel):
    case_number: str
    workspace: WorkspaceContext
    asset_root: Path
    case_details_path: Path


class SourceArtifact(BaseModel):
    source_type: Literal[
        "case_details",
        "press_release",
        "charge_sheet",
        "court_order",
        "bolpatra",
        "news",
    ]
    title: str
    raw_path: Path
    markdown_path: Path
    source_url: str | None = None
    external_url: str | None = None
    identifier: str | None = None
    publication_date: str | None = None
    notes: str | None = None


class SourceBundle(BaseModel):
    case_number: str
    workspace: WorkspaceContext
    asset_root: Path
    case_details_path: Path
    source_artifacts: list[SourceArtifact] = Field(default_factory=list)
    case_details_artifact: SourceArtifact | None = None
    press_release_artifact: SourceArtifact | None = None
    charge_sheet_artifact: SourceArtifact | None = None
    news_artifacts: list[SourceArtifact] = Field(default_factory=list)


class PublishInput(BaseModel):
    case_number: str
    source_bundle: SourceBundle
    draft_path: Path


class PublishedCaseResult(BaseModel):
    case_id: int
    entity_ids: list[int] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    updated_fields: list[str] = Field(default_factory=list)


class WorkflowResult(BaseModel):
    case_number: str
    published: bool
    case_id: int | None = None
