from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from jawafdehi_agentspan.models import CaseInitialization, WorkspaceContext


def raw_sources_dir(root_dir: Path) -> Path:
    return root_dir / "sources" / "raw"


def markdown_sources_dir(root_dir: Path) -> Path:
    return root_dir / "sources" / "markdown"


def build_workspace_context(root_dir: Path) -> WorkspaceContext:
    root_dir = root_dir.resolve()
    logs_dir = root_dir / "logs"
    data_dir = root_dir / "data"
    sources_raw = raw_sources_dir(root_dir)
    sources_markdown = markdown_sources_dir(root_dir)
    memory_file = root_dir / "MEMORY.md"

    logs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    sources_raw.mkdir(parents=True, exist_ok=True)
    sources_markdown.mkdir(parents=True, exist_ok=True)
    if not memory_file.exists():
        memory_file.write_text("# MEMORY\n\n", encoding="utf-8")

    return WorkspaceContext(
        root_dir=root_dir,
        logs_dir=logs_dir,
        data_dir=data_dir,
        memory_file=memory_file,
        sources=[],
    )


def create_workspace(case_number: str) -> WorkspaceContext:
    runs_dir = Path.cwd() / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    root_dir = runs_dir / f"jawaf-{timestamp}-{case_number}"
    root_dir.mkdir(parents=False, exist_ok=False)
    return build_workspace_context(root_dir)


def build_case_initialization(
    case_number: str,
    workspace_root: Path,
    fetch_case_details: Callable[[str, Path], Awaitable[str]],
    *,
    asset_root: Path,
) -> CaseInitialization:
    workspace = build_workspace_context(workspace_root)
    case_details_path = workspace.root_dir / f"case_details-{case_number}.md"
    content = asyncio.run(fetch_case_details(case_number, case_details_path))
    summary_path = workspace.logs_dir / "case-summary.md"
    summary_path.write_text(
        f"# Case Summary\n\n- Case number: {case_number}\n\n{content[:1200]}\n",
        encoding="utf-8",
    )
    return CaseInitialization(
        case_number=case_number,
        workspace=workspace,
        asset_root=asset_root,
        case_details_path=case_details_path,
    )
