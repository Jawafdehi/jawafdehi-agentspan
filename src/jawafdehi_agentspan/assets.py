from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ciaa_workflow_root() -> Path:
    return _repo_root() / "assets" / "ciaa_caseworker"


def ciaa_prompts_root() -> Path:
    return _repo_root() / "assets" / "prompts"


def ciaa_case_template_path() -> Path:
    return ciaa_prompts_root() / "case-template.md"


def ciaa_ag_index_path() -> Path:
    return ciaa_data_root() / "ag_index.csv"


def ciaa_press_releases_path() -> Path:
    return ciaa_data_root() / "ciaa-press-releases.csv"


def ciaa_assets_root() -> Path:
    return _repo_root() / "assets"


def ciaa_data_root() -> Path:
    # Prefer repository-managed data under files/data, keep assets/data fallback.
    candidates = [
        _repo_root() / "files" / "data",
        ciaa_assets_root() / "data",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]
