from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from jawafdehi_agentspan.mcp_adapters import MCPToolAdapter
from jawafdehi_agentspan.models import CaseInitialization, WorkspaceContext
from jawafdehi_agentspan.settings import Settings, get_settings


def global_store_root(settings: Settings | None = None) -> Path:
    return (settings or get_settings()).global_store_root.resolve()


def runs_root(settings: Settings | None = None) -> Path:
    return (settings or get_settings()).runs_root.resolve()


def global_case_dir(case_number: str, settings: Settings | None = None) -> Path:
    return global_store_root(settings) / "cases" / case_number


def global_raw_sources_dir(case_number: str, settings: Settings | None = None) -> Path:
    return global_case_dir(case_number, settings) / "sources" / "raw"


def global_markdown_sources_dir(
    case_number: str, settings: Settings | None = None
) -> Path:
    return global_case_dir(case_number, settings) / "sources" / "markdown"


def global_news_raw_dir(case_number: str, settings: Settings | None = None) -> Path:
    return global_case_dir(case_number, settings) / "sources" / "news" / "raw"


def global_news_markdown_dir(
    case_number: str, settings: Settings | None = None
) -> Path:
    return global_case_dir(case_number, settings) / "sources" / "news" / "markdown"


def ensure_case_store_dirs(case_number: str, settings: Settings | None = None) -> None:
    for path in (
        global_raw_sources_dir(case_number, settings),
        global_markdown_sources_dir(case_number, settings),
        global_news_raw_dir(case_number, settings),
        global_news_markdown_dir(case_number, settings),
    ):
        path.mkdir(parents=True, exist_ok=True)


def build_workspace_context(root_dir: Path) -> WorkspaceContext:
    root_dir = root_dir.resolve()
    logs_dir = root_dir / "logs"
    data_dir = root_dir / "data"
    memory_file = root_dir / "MEMORY.md"

    logs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
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
    runs_dir = runs_root()
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    root_dir = runs_dir / f"jawaf-{timestamp}-{case_number}"
    root_dir.mkdir(parents=False, exist_ok=False)
    return build_workspace_context(root_dir)


async def _fetch_case_details(
    adapter: MCPToolAdapter, case_number: str, output_path: Path
) -> str:
    result = await adapter.call_text(
        "ngm_extract_case_data",
        {
            "court_identifier": "special",
            "case_number": case_number,
            "file_path": str(output_path),
        },
    )
    msg = result.lower()
    if "429" in msg or "too many requests" in msg or "rate limit" in msg:
        raise RuntimeError(f"NGM API rate-limited for {case_number}: {result}")
    return output_path.read_text(encoding="utf-8")


def build_case_initialization(
    case_number: str,
    workspace_root: Path,
    adapter: MCPToolAdapter,
    *,
    asset_root: Path,
) -> CaseInitialization:
    workspace = build_workspace_context(workspace_root)
    ensure_case_store_dirs(case_number)
    case_details_path = workspace.data_dir / f"case_details-{case_number}.md"
    content = asyncio.run(_fetch_case_details(adapter, case_number, case_details_path))
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
