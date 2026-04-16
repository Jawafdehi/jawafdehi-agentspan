from __future__ import annotations

from pathlib import Path

from jawafdehi_agentspan.tools import (
    append_workspace_file,
    list_workspace_files,
    read_reference_file,
    read_workspace_file,
    write_workspace_file,
)


def test_workspace_file_tools_roundtrip(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "notes.md"

    write_workspace_file(str(target), "hello", str(root))
    append_workspace_file(str(target), "\nworld", str(root))

    assert read_workspace_file(str(target), str(root)) == "hello\nworld"
    assert str(target) in list_workspace_files(str(root))


def test_read_reference_file_can_read_assets(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    from jawafdehi_agentspan.assets import ciaa_case_template_path

    content = read_reference_file(str(ciaa_case_template_path()), str(root))
    assert "# Case Draft Template" in content
