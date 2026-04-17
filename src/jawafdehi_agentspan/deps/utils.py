from __future__ import annotations

from pathlib import Path
from typing import Any

from jawafdehi_agentspan.assets import ciaa_workflow_root


def ensure_within_directory(root: Path, path: Path, *, label: str) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as err:
        raise RuntimeError(f"Path is outside the allowed {label} root: {path}") from err


def ensure_within_workspace(workspace_root: Path, path: Path) -> None:
    ensure_within_directory(workspace_root, path, label="workspace")


def ensure_within_global_store(global_store_root: Path, path: Path) -> None:
    ensure_within_directory(global_store_root, path, label="global store")


def ensure_within_workspace_or_assets(path: Path) -> None:
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(ciaa_workflow_root().resolve())
        return
    except ValueError as err:
        raise RuntimeError(f"Path is outside the allowed asset root: {path}") from err


def render_review_markdown(critique: Any) -> str:
    strengths = "\n".join(f"- {item}" for item in critique.strengths) or "- None"
    improvements = "\n".join(f"- {item}" for item in critique.improvements) or "- None"
    blockers = "\n".join(f"- {item}" for item in critique.blockers) or "- None"
    return (
        "# Draft Review\n\n"
        "## Overall Outcome\n\n"
        f"**`{critique.outcome.value}`**\n\n"
        f"## Score\n\n{critique.score}\n\n"
        "## Strengths\n\n"
        f"{strengths}\n\n"
        "## Improvements\n\n"
        f"{improvements}\n\n"
        "## Blockers\n\n"
        f"{blockers}\n"
    )
