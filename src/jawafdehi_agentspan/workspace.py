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
    return global_case_dir(case_number, settings) / "news" / "raw"


def global_news_markdown_dir(
    case_number: str, settings: Settings | None = None
) -> Path:
    return global_case_dir(case_number, settings) / "news" / "markdown"


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
    tmp_dir = root_dir / "tmp"

    logs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    return WorkspaceContext(
        root_dir=root_dir,
        logs_dir=logs_dir,
        data_dir=data_dir,
        sources=[],
    )


def create_workspace(
    case_number: str, settings: Settings | None = None
) -> WorkspaceContext:
    case_dir = global_case_dir(case_number, settings)
    tmp_dir = case_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    root_dir = tmp_dir / f"run-{timestamp}"
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
    if not output_path.is_file():
        raise RuntimeError(
            f"NGM tool failed to write case details for {case_number}: {result}"
        )
    return output_path.read_text(encoding="utf-8")


def build_case_initialization(
    case_number: str,
    workspace_root: Path,
    adapter: MCPToolAdapter,
    *,
    asset_root: Path,
    settings: Settings | None = None,
) -> CaseInitialization:
    workspace = build_workspace_context(workspace_root)
    ensure_case_store_dirs(case_number, settings)
    case_details_path = workspace.data_dir / f"case_details-{case_number}.md"
    asyncio.run(_fetch_case_details(adapter, case_number, case_details_path))
    return CaseInitialization(
        case_number=case_number,
        workspace=workspace,
        asset_root=asset_root,
        case_details_path=case_details_path,
    )
