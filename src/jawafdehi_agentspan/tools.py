from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agentspan.agents import tool

from jawafdehi_agentspan.assets import ciaa_workflow_root
from jawafdehi_agentspan.dependencies import (
    ensure_within_workspace,
    get_dependencies,
)
from jawafdehi_agentspan.models import CaseInitialization, PublishInput, SourceBundle
from jawafdehi_agentspan.workspace import build_case_initialization


def _run_async(awaitable):
    return asyncio.run(awaitable)


def _workspace_root(workspace_root: str) -> Path:
    path = Path(workspace_root).resolve()
    if not path.is_dir():
        raise RuntimeError(f"Workspace does not exist: {workspace_root}")
    return path


def _validate_workspace_path(path: str, workspace_root: str) -> Path:
    resolved = Path(path).resolve()
    ensure_within_workspace(_workspace_root(workspace_root), resolved)
    return resolved


@tool(isolated=False)
def list_workspace_files(workspace_root: str, pattern: str = "**/*") -> list[str]:
    root = _workspace_root(workspace_root)
    return [str(path) for path in sorted(root.glob(pattern)) if path.is_file()]


@tool(isolated=False)
def read_workspace_file(file_path: str, workspace_root: str) -> str:
    path = _validate_workspace_path(file_path, workspace_root)
    return path.read_text(encoding="utf-8")


@tool(isolated=False)
def read_reference_file(file_path: str, workspace_root: str) -> str:
    path = Path(file_path).resolve()
    try:
        ensure_within_workspace(_workspace_root(workspace_root), path)
    except ValueError:
        path.relative_to(ciaa_workflow_root().resolve())
    return path.read_text(encoding="utf-8")


@tool(isolated=False)
def write_workspace_file(file_path: str, content: str, workspace_root: str) -> str:
    path = _validate_workspace_path(file_path, workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


@tool(isolated=False)
def append_workspace_file(file_path: str, content: str, workspace_root: str) -> str:
    path = _validate_workspace_path(file_path, workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content)
    return str(path)


@tool(isolated=False)
def download_file(url: str, output_path: str, workspace_root: str) -> str:
    path = _validate_workspace_path(output_path, workspace_root)
    downloaded = _run_async(get_dependencies().fetcher.download(url, path))
    return str(downloaded)


@tool(isolated=False)
def fetch_url(url: str) -> str:
    return _run_async(get_dependencies().fetcher.fetch_text(url))


@tool(isolated=False)
def brave_search(query: str, count: int = 8) -> list[dict[str, str]]:
    return _run_async(get_dependencies().search_client.search(query, count=count))


@tool(isolated=False)
def ngm_extract_case_data(
    court_identifier: str, case_number: str, file_path: str, workspace_root: str
) -> str:
    path = _validate_workspace_path(file_path, workspace_root)
    return _run_async(
        get_dependencies().adapter.call_text(
            "ngm_extract_case_data",
            {
                "court_identifier": court_identifier,
                "case_number": case_number,
                "file_path": str(path),
            },
        )
    )


@tool(isolated=False)
def convert_to_markdown(file_path: str, output_path: str, workspace_root: str) -> str:
    raw_path = _validate_workspace_path(file_path, workspace_root)
    md_path = _validate_workspace_path(output_path, workspace_root)
    return _run_async(
        get_dependencies().adapter.convert_to_markdown(
            {"file_path": str(raw_path), "output_path": str(md_path)}
        )
    )


@tool(isolated=False)
def initialize_casework_step(case_number: str, workspace_root: str) -> dict[str, Any]:
    initialization = build_case_initialization(
        case_number,
        _workspace_root(workspace_root),
        get_dependencies().adapter,
        asset_root=ciaa_workflow_root(),
    )
    return json.loads(initialization.model_dump_json())


@tool(isolated=False)
def gather_sources_step(initialization_json: str) -> dict[str, Any]:
    initialization = CaseInitialization.model_validate_json(initialization_json)
    bundle = _run_async(
        get_dependencies().source_gatherer.gather_sources(initialization)
    )
    return json.loads(bundle.model_dump_json())


@tool(isolated=False)
def gather_news_step(source_bundle_json: str) -> dict[str, Any]:
    bundle = SourceBundle.model_validate_json(source_bundle_json)
    updated = _run_async(get_dependencies().news_gatherer.gather_news(bundle))
    return json.loads(updated.model_dump_json())


@tool(isolated=False)
def publish_case_step(publish_input_json: str) -> dict[str, Any]:
    publish_input = PublishInput.model_validate_json(publish_input_json)
    result = _run_async(
        get_dependencies().publish_finalizer.publish_and_finalize(publish_input)
    )
    return json.loads(result.model_dump_json())
