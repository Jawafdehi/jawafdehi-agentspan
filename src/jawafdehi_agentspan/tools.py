from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from agentspan.agents import tool

from jawafdehi_agentspan.assets import ciaa_workflow_root
from jawafdehi_agentspan.dependencies import get_dependencies
from jawafdehi_agentspan.models import CaseInitialization, PublishInput, SourceBundle
from jawafdehi_agentspan.settings import get_settings

logger = logging.getLogger(__name__)


def _run_async(awaitable):
    return asyncio.run(awaitable)


def _allowed_roots() -> list[Path]:
    settings = get_settings()
    return [settings.global_store_root.resolve(), settings.runs_root.resolve()]


def _validate_path(path: str) -> Path:
    resolved = Path(path).resolve()
    for root in _allowed_roots():
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise RuntimeError(
        f"Path is outside the allowed roots (global_store, runs): {path}"
    )


def _validate_readable_path(path: str) -> Path:
    """Like _validate_path but also allows assets."""
    resolved = Path(path).resolve()
    assets_root = ciaa_workflow_root().resolve().parent
    if resolved.is_relative_to(assets_root):
        return resolved
    return _validate_path(path)


def _validate_case_directory(path: str) -> Path:
    resolved = _validate_path(path)
    settings = get_settings()
    cases_root = (settings.global_store_root.resolve() / "cases").resolve()

    try:
        relative = resolved.relative_to(cases_root)
    except ValueError as exc:
        raise RuntimeError(
            f"Directory must be inside a case directory under {cases_root}: {path}"
        ) from exc

    if len(relative.parts) < 2:
        raise RuntimeError(
            f"Directory must be inside files/cases/{{case-number}}/...: {path}"
        )

    return resolved


_READ_FILE_MAX_BYTES = 100_000  # 100 KB — prevents 413 from huge log files


@tool(isolated=False)
def read_file(file_path: str) -> str:
    path = _validate_readable_path(file_path)
    if path.suffix == ".log":
        raise RuntimeError(
            f"Reading .log files is not allowed: {path}. "
            "Log files are large debug artifacts — ignore them."
        )
    size = path.stat().st_size
    if size > _READ_FILE_MAX_BYTES:
        raise RuntimeError(
            f"File too large to read ({size:,} bytes > "
            f"{_READ_FILE_MAX_BYTES:,} limit): {path}. "
            "Use grepNew to search for specific content instead."
        )
    return path.read_text(encoding="utf-8")


@tool(isolated=False)
def write_file(file_path: str, content: str) -> str:
    path = _validate_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


@tool(isolated=False)
def append_file(file_path: str, content: str) -> str:
    path = _validate_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content)
    return str(path)


@tool(isolated=False)
def mkdir(directory_path: str) -> str:
    path = _validate_case_directory(directory_path)
    already_exists = path.is_dir()
    path.mkdir(parents=True, exist_ok=True)

    if already_exists:
        warning = f"Warning: directory already exists: {path}"
        logger.warning(warning)
        return warning

    return f"Created directory: {path}"


@tool(isolated=False)
def list_files(directory: str, pattern: str = "**/*") -> list[str]:
    """List files and directories matching pattern.

    Files show line count; directories end with /.
    """
    root = _validate_readable_path(directory)
    results = []
    for p in sorted(root.glob(pattern)):
        if p.is_dir():
            results.append(f"{p}/")
        else:
            try:
                line_count = sum(1 for _ in p.open("rb"))
            except OSError:
                line_count = 0
            results.append(f"{p} ({line_count} lines)")
    return results


@tool(isolated=False)
def grepNew(pattern: str, path: str, extra_args: str = "") -> str:
    """Run system grep on path.

    The path may be a file or directory, and it must be within allowed roots.
    """
    resolved = _validate_readable_path(path)
    cmd = ["grep", "-rn", pattern, str(resolved)]
    if extra_args:
        cmd = ["grep"] + extra_args.split() + [pattern, str(resolved)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = result.stdout
    if result.returncode not in (0, 1):  # 1 = no matches, not an error
        output += f"\n[stderr]: {result.stderr}"
    return output or "(no matches)"


@tool(isolated=False)
def tree(directory: str) -> str:
    """Show directory tree with file sizes. Directories end with /."""
    root = _validate_readable_path(directory)

    lines = [str(root) + "/"]

    def _walk(path: Path, prefix: str) -> None:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk(entry, prefix + extension)
            else:
                size = entry.stat().st_size
                if size >= 1024 * 1024:
                    size_str = f"{size / 1024 / 1024:.1f}MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size}B"
                lines.append(f"{prefix}{connector}{entry.name} ({size_str})")

    _walk(root, "")
    return "\n".join(lines)


@tool(isolated=False)
def download_file(url: str, output_path: str) -> str:
    path = _validate_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
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
    court_identifier: str, case_number: str, file_path: str
) -> str:
    path = _validate_path(file_path)
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
def convert_to_markdown(file_path: str, output_path: str) -> str:
    raw_path = _validate_path(file_path)
    md_path = _validate_path(output_path)
    return _run_async(
        get_dependencies().adapter.convert_to_markdown(
            {"file_path": str(raw_path), "output_path": str(md_path)}
        )
    )


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
