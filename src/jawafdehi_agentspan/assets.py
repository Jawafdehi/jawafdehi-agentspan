from __future__ import annotations

from pathlib import Path


def ciaa_workflow_root() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "ciaa_caseworker"


def ciaa_prompts_root() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "prompts"


def ciaa_case_template_path() -> Path:
    return ciaa_prompts_root() / "case-template.md"


def ciaa_ag_index_path() -> Path:
    return ciaa_workflow_root() / "data" / "ag_index.csv"


def ciaa_press_releases_path() -> Path:
    return ciaa_workflow_root() / "data" / "ciaa-press-releases.csv"


def ciaa_assets_root() -> Path:
    return Path(__file__).resolve().parents[2] / "assets"
