from __future__ import annotations

from pathlib import Path

import pytest

from jawafdehi_agentspan.settings import get_settings
from jawafdehi_agentspan.tools import (
    append_file,
    list_files,
    mkdir,
    read_file,
    write_file,
)


def test_file_tools_roundtrip(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    target = root / "cases" / "081-CR-0046" / "notes.md"

    write_file(str(target), "hello")
    append_file(str(target), "\nworld")

    assert target.read_text(encoding="utf-8") == "hello\nworld"
    assert any(str(target) in entry for entry in list_files(str(root)))


def test_read_file_can_read_assets(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    from jawafdehi_agentspan.assets import ciaa_case_template_path

    content = read_file(str(ciaa_case_template_path()))
    assert "# Case Draft Template" in content


def test_file_tools_reject_escape(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    outside = tmp_path / "outside.txt"

    with pytest.raises(RuntimeError, match="outside the allowed roots"):
        write_file(str(outside), "nope")


def test_mkdir_creates_case_directory(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    target = root / "cases" / "081-CR-0046" / "sources" / "raw"

    result = mkdir(str(target))

    assert target.is_dir()
    assert result == f"Created directory: {target}"


def test_mkdir_warns_when_directory_exists(tmp_path: Path, monkeypatch, caplog):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    target = root / "cases" / "081-CR-0046" / "sources"
    target.mkdir(parents=True, exist_ok=True)

    with caplog.at_level("WARNING"):
        result = mkdir(str(target))

    assert result == f"Warning: directory already exists: {target}"
    assert f"Warning: directory already exists: {target}" in caplog.text


def test_mkdir_rejects_non_case_directory(tmp_path: Path, monkeypatch):
    root = tmp_path / "global_store"
    monkeypatch.setenv("GLOBAL_STORE_ROOT", str(root))
    get_settings.cache_clear()
    target = root / "data" / "scratch"

    with pytest.raises(RuntimeError, match=r"inside a case directory under"):
        mkdir(str(target))
