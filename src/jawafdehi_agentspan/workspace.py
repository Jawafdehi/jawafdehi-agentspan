from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jawafdehi_agentspan.models import WorkspaceContext


def create_workspace(case_number: str) -> WorkspaceContext:
    runs_dir = Path.cwd() / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    root_dir = runs_dir / f"jawaf-{timestamp}-{case_number}"
    root_dir.mkdir(parents=False, exist_ok=False)
    logs_dir = root_dir / "logs"
    data_dir = root_dir / "data"
    sources_raw_dir = root_dir / "sources" / "raw"
    sources_markdown_dir = root_dir / "sources" / "markdown"
    memory_file = root_dir / "MEMORY.md"

    logs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    sources_raw_dir.mkdir(parents=True, exist_ok=True)
    sources_markdown_dir.mkdir(parents=True, exist_ok=True)
    memory_file.write_text("# MEMORY\n\n", encoding="utf-8")

    return WorkspaceContext(
        root_dir=root_dir,
        logs_dir=logs_dir,
        data_dir=data_dir,
        sources_raw_dir=sources_raw_dir,
        sources_markdown_dir=sources_markdown_dir,
        memory_file=memory_file,
    )
