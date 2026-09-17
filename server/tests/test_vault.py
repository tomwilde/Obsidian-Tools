import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import config
from tools import common
from tools.files import _list_files, list_files
from tools.folders import _list_folders, list_folders


def test_determine_root_dir_reads_config(tmp_path):
    ini = tmp_path / "config.ini"
    ini.write_text(f"[Obsidian]\nRootDir = {tmp_path}\n")
    assert config.determine_root_dir(ini) == tmp_path


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        config.load_config(tmp_path / "missing.ini")


def test_list_folders_lists_directories(tmp_path, monkeypatch):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "nested").mkdir()
    (tmp_path / "file.md").write_text("x")
    (tmp_path / "nested" / "inner").mkdir()
    monkeypatch.setattr(common, "rootdir", tmp_path)
    assert asyncio.run(list_folders("")) == ["alpha", "beta", "nested"]
    assert asyncio.run(list_folders("nested")) == ["inner"]


@pytest.mark.parametrize("path", [".", ".."])
def test_list_folders_forbids_dot_paths(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_folders(path))
    assert "403" in str(exc_info.value)


def test_list_folders_missing_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_folders("does/not/exist"))
    assert "Not a directory" in str(exc_info.value)


def test_list_folders_catches_general_failure():
    with pytest.raises(ToolError) as exc_info:
        _list_folders(None, "")
    assert "General error" in str(exc_info.value)


def test_list_files_lists_files(tmp_path, monkeypatch):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "inner").mkdir()
    (tmp_path / "plan.md").write_text("x")
    (tmp_path / "note.md").write_text("y")
    (tmp_path / "nested" / "deep.md").write_text("z")
    monkeypatch.setattr(common, "rootdir", tmp_path)
    assert asyncio.run(list_files("")) == ["note.md", "plan.md"]
    assert asyncio.run(list_files("nested")) == ["deep.md"]


@pytest.mark.parametrize("path", [".", ".."])
def test_list_files_forbids_dot_paths(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_files(path))
    assert "403" in str(exc_info.value)


def test_list_files_missing_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_files("does/not/exist"))
    assert "Not a directory" in str(exc_info.value)


def test_list_files_catches_general_failure():
    with pytest.raises(ToolError) as exc_info:
        _list_files(None, "")
    assert "General error" in str(exc_info.value)