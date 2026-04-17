from __future__ import annotations

from pathlib import Path

import pytest

from jawafdehi_agentspan.settings import get_settings
from jawafdehi_agentspan.tools import (
    append_global_source_file,
    append_workspace_file,
    list_global_source_files,
    list_workspace_files,
    read_reference_file,
    write_global_source_file,
    write_workspace_file,
)


def test_workspace_file_tools_roundtrip(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "notes.md"

    write_workspace_file(str(target), "hello", str(root))
    append_workspace_file(str(target), "\nworld", str(root))

    assert target.read_text(encoding="utf-8") == "hello\nworld"
    assert str(target) in list_workspace_files(str(root))


def test_read_reference_file_can_read_assets(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    from jawafdehi_agentspan.assets import ciaa_case_template_path

    content = read_reference_file(str(ciaa_case_template_path()), str(root))
    assert "# Case Draft Template" in content


def test_global_source_file_tools_roundtrip(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    target = root / "cases" / "081-CR-0046" / "sources" / "markdown" / "charge-sheet.md"

    write_global_source_file(str(target), "hello")
    append_global_source_file(str(target), "\nworld")

    assert target.read_text(encoding="utf-8") == "hello\nworld"
    assert str(target) in list_global_source_files()


def test_global_source_file_tools_reject_escape(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    outside = tmp_path / "outside.txt"

    with pytest.raises(RuntimeError, match="global store"):
        write_global_source_file(str(outside), "nope")
