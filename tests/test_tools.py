from __future__ import annotations

import json
from pathlib import Path

import pytest

from jawafdehi_agentspan.run_service import RunService
from jawafdehi_agentspan.settings import get_settings
from jawafdehi_agentspan.tools import (
    append_file,
    list_files,
    mkdir,
    read_file,
    write_file,
)


def _set_tool_env(monkeypatch, root: Path) -> None:
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    monkeypatch.setenv("RUNS_ROOT", str(root / "runs"))
    monkeypatch.setenv("JAWAFDEHI_API_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()


def test_file_tools_roundtrip(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    _set_tool_env(monkeypatch, root)
    target = root / "cases" / "081-CR-0046" / "notes.md"

    write_file(str(target), "hello")
    append_file(str(target), "\nworld")

    assert target.read_text(encoding="utf-8") == "hello\nworld"
    assert any(str(target) in entry for entry in list_files(str(root)))


def test_read_file_can_read_assets(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    _set_tool_env(monkeypatch, root)
    from jawafdehi_agentspan.assets import ciaa_case_template_path

    content = read_file(str(ciaa_case_template_path()))
    assert "# Case Draft Template" in content


def test_file_tools_reject_escape(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    _set_tool_env(monkeypatch, root)
    outside = tmp_path / "outside.txt"

    with pytest.raises(RuntimeError, match="outside the allowed roots"):
        write_file(str(outside), "nope")


def test_mkdir_creates_case_directory(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    _set_tool_env(monkeypatch, root)
    target = root / "cases" / "081-CR-0046" / "sources" / "raw"

    result = mkdir(str(target))

    assert target.is_dir()
    assert result == f"Created directory: {target}"


def test_mkdir_warns_when_directory_exists(tmp_path: Path, monkeypatch, caplog):
    root = tmp_path / "global_store"
    _set_tool_env(monkeypatch, root)
    target = root / "cases" / "081-CR-0046" / "sources"
    target.mkdir(parents=True, exist_ok=True)

    with caplog.at_level("WARNING"):
        result = mkdir(str(target))

    assert result == f"Warning: directory already exists: {target}"
    assert f"Warning: directory already exists: {target}" in caplog.text


def test_mkdir_rejects_non_case_directory(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    _set_tool_env(monkeypatch, root)
    target = root / "data" / "scratch"

    with pytest.raises(RuntimeError, match=r"inside a case directory under"):
        mkdir(str(target))


def test_persist_payload_safe_artifacts_marks_unmapped_claims_invalid(tmp_path: Path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    draft_final_path = workspace_root / "draft-final.md"
    draft_final_path.write_text("## Title\nExample\n", encoding="utf-8")

    (workspace_root / "traceability-map.json").write_text(
        json.dumps(
            [
                {
                    "claim_text": "Unmapped assertion",
                    "section": "description",
                    "source_refs": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (workspace_root / "validation-report.json").write_text(
        json.dumps(
            {
                "is_valid": True,
                "missing_sections": [],
                "unmapped_claims": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    RunService._persist_payload_safe_artifacts(workspace_root, draft_final_path)

    payload = json.loads(
        (workspace_root / "validation-report.json").read_text(encoding="utf-8")
    )
    assert payload["is_valid"] is False
    assert payload["unmapped_claims"] == ["Unmapped assertion"]
    assert "unmapped claims found" in payload["errors"]
