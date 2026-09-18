import asyncio
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import config
import indexer
from tools import common
from tools.files import _list_files, _read_file, list_files, read_file
from tools.folders import _list_folders, list_folders
from tools.rag import _rag_query, rag_flush_index, rag_query


class FakeIndex:
    def __init__(self, ready, matches=None):
        self.ready = ready
        self.matches = matches or []
        self.flushed = False
        self.built = False

    def query(self, query_text):
        return self.matches

    def flush(self):
        self.flushed = True

    def build(self):
        self.built = True


def test_determine_root_dir_reads_config(tmp_path, monkeypatch):
    monkeypatch.delenv("VAULT_DIR", raising=False)
    ini = tmp_path / "config.ini"
    ini.write_text(f"[Obsidian]\nRootDir = {tmp_path}\n")
    assert config.determine_root_dir(ini) == tmp_path


def test_determine_root_dir_prefers_vault_dir_environment_variable(tmp_path, monkeypatch):
    configured = tmp_path / "from-config"
    configured.mkdir()
    overridden = tmp_path / "from-env"
    overridden.mkdir()
    ini = tmp_path / "config.ini"
    ini.write_text(f"[Obsidian]\nRootDir = {configured}\n")
    monkeypatch.setenv("VAULT_DIR", str(overridden))
    assert config.determine_root_dir(ini) == overridden


def test_determine_excluded_dirs_reads_config(tmp_path):
    ini = tmp_path / "config.ini"
    ini.write_text("[Obsidian]\nRootDir = /tmp\nExcludedDirs = .obsidian, private/notes\n")
    assert config.determine_excluded_dirs(ini) == (Path(".obsidian"), Path("private/notes"))


def test_determine_excluded_dirs_supports_newline_values(tmp_path):
    ini = tmp_path / "config.ini"
    ini.write_text("[Obsidian]\nRootDir = /tmp\nExcludedDirs = one\n  two/sub\n")
    assert config.determine_excluded_dirs(ini) == (Path("one"), Path("two/sub"))


def test_determine_excluded_dirs_rejects_parent_traversal(tmp_path):
    ini = tmp_path / "config.ini"
    ini.write_text("[Obsidian]\nRootDir = /tmp\nExcludedDirs = ../secret\n")
    with pytest.raises(ValueError):
        config.determine_excluded_dirs(ini)


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
    monkeypatch.setattr(common, "excluded_dirs", ())
    assert asyncio.run(list_folders("")) == ["alpha", "beta", "nested"]
    assert asyncio.run(list_folders("/")) == ["alpha", "beta", "nested"]
    assert asyncio.run(list_folders("nested")) == ["inner"]
    assert asyncio.run(list_folders("/nested")) == ["inner"]


@pytest.mark.parametrize("path", [".", ".."])
def test_list_folders_forbids_dot_paths(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_folders(path))
    assert "403" in str(exc_info.value)


@pytest.mark.parametrize("path", ["../", "../etc", "/../etc", "/../../"])
def test_list_folders_forbids_parent_traversal(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_folders(path))
    assert "403" in str(exc_info.value)


def test_list_folders_missing_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_folders("does/not/exist"))
    assert "Not a directory" in str(exc_info.value)


def test_list_folders_hides_excluded_directories(tmp_path, monkeypatch):
    (tmp_path / "public").mkdir()
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "nested").mkdir()
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", (Path("private"),))
    assert asyncio.run(list_folders("")) == ["public"]
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_folders("private"))
    assert "404" in str(exc_info.value)


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
    monkeypatch.setattr(common, "excluded_dirs", ())
    assert asyncio.run(list_files("")) == ["note.md", "plan.md"]
    assert asyncio.run(list_files("/")) == ["note.md", "plan.md"]
    assert asyncio.run(list_files("nested")) == ["deep.md"]
    assert asyncio.run(list_files("/nested")) == ["deep.md"]


@pytest.mark.parametrize("path", [".", ".."])
def test_list_files_forbids_dot_paths(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_files(path))
    assert "403" in str(exc_info.value)


@pytest.mark.parametrize("path", ["../", "../etc", "/../etc", "/../../"])
def test_list_files_forbids_parent_traversal(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_files(path))
    assert "403" in str(exc_info.value)


def test_list_files_missing_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(list_files("does/not/exist"))
    assert "Not a directory" in str(exc_info.value)


def test_list_files_catches_general_failure():
    with pytest.raises(ToolError) as exc_info:
        _list_files(None, "")
    assert "General error" in str(exc_info.value)


def test_list_files_filters_by_extension(tmp_path, monkeypatch):
    (tmp_path / "plan.md").write_text("x")
    (tmp_path / "notes.txt").write_text("y")
    (tmp_path / "todo.txt").write_text("z")
    (tmp_path / "data.csv").write_text("w")
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    assert asyncio.run(list_files("", "txt")) == ["notes.txt", "todo.txt"]
    assert asyncio.run(list_files("", ".md")) == ["plan.md"]
    assert asyncio.run(list_files("", "json")) == []
    assert asyncio.run(list_files("")) == ["data.csv", "notes.txt", "plan.md", "todo.txt"]


def test_read_file_returns_contents(tmp_path, monkeypatch):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "note.md").write_text("hello world")
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    assert asyncio.run(read_file("nested/note.md")) == "hello world"
    assert asyncio.run(read_file("/nested/note.md")) == "hello world"


@pytest.mark.parametrize("path", [".", ".."])
def test_read_file_forbids_dot_paths(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(read_file(path))
    assert "403" in str(exc_info.value)


@pytest.mark.parametrize("path", ["../", "../etc/passwd", "/../etc/passwd", "/../../secret.md"])
def test_read_file_forbids_parent_traversal(path, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(read_file(path))
    assert "403" in str(exc_info.value)


def test_read_file_missing_file_raises_404(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(read_file("does/not/exist.md"))
    assert "404" in str(exc_info.value)


def test_read_file_directory_raises_404(tmp_path, monkeypatch):
    (tmp_path / "nested").mkdir()
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", ())
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(read_file("nested"))
    assert "404" in str(exc_info.value)


def test_read_file_hidden_directory_raises_404(tmp_path, monkeypatch):
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "note.md").write_text("secret")
    monkeypatch.setattr(common, "rootdir", tmp_path)
    monkeypatch.setattr(common, "excluded_dirs", (Path("private"),))
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(read_file("private/note.md"))
    assert "404" in str(exc_info.value)


def test_read_file_catches_general_failure():
    with pytest.raises(ToolError) as exc_info:
        _read_file(None, "")
    assert "General error" in str(exc_info.value)


def test_rag_query_returns_503_until_index_ready(monkeypatch):
    monkeypatch.setattr(indexer, "rag_index", FakeIndex(ready=False))
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(rag_query("what is this vault about?"))
    assert "503" in str(exc_info.value)


def test_rag_query_returns_matches_when_ready(monkeypatch):
    matches = [{"file": "note.md", "text": "hello", "score": 0.5}]
    monkeypatch.setattr(indexer, "rag_index", FakeIndex(ready=True, matches=matches))
    assert asyncio.run(rag_query("anything")) == matches
    assert _rag_query("anything") == matches


def test_rag_flush_index_triggers_full_reindex(monkeypatch):
    fake = FakeIndex(ready=True)
    monkeypatch.setattr(indexer, "rag_index", fake)
    assert asyncio.run(rag_flush_index()) == 200
    assert fake.flushed is True
    assert fake.built is True


def test_rag_flush_index_catches_general_failure(monkeypatch):
    monkeypatch.setattr(indexer, "rag_index", None)
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(rag_flush_index())
    assert "General error" in str(exc_info.value)


class OrthogonalEmbedding:
    def __call__(self, texts):
        return [
            [1.0 if i == offset % 8 else 0.0 for i in range(8)]
            for offset in range(len(texts))
        ]


def test_split_sentences_splits_on_punctuation_and_lines(tmp_path):
    imp = indexer.Indexer(tmp_path)
    text = "First sentence. Second one!\n\n# Heading\nA line without punctuation\nThird?"
    assert imp._split_sentences(text) == [
        "First sentence.",
        "Second one!",
        "# Heading",
        "A line without punctuation",
        "Third?",
    ]


def test_split_sentences_hard_splits_very_long_segments(tmp_path):
    imp = indexer.Indexer(tmp_path)
    long = "word " * (indexer.MAX_SENTENCE_CHARS + 100)
    parts = imp._split_sentences(long)
    assert len(parts) > 1
    assert all(len(part) <= indexer.MAX_CHUNK_CHARS for part in parts)
    assert "".join(parts).replace(" ", "") == long.strip().replace(" ", "")


def test_group_chunks_splits_at_low_similarity(tmp_path):
    imp = indexer.Indexer(tmp_path)
    sentences = ["The cat.", "The dog.", "Python code.", "Rust code."]
    similarities = [0.9, 0.1, 0.8]
    chunks = imp._group_chunks(sentences, similarities, threshold=0.5, min_chunk_chars=0)
    assert chunks == ["The cat. The dog.", "Python code. Rust code."]


def test_group_chunks_respects_max_size(tmp_path):
    imp = indexer.Indexer(tmp_path)
    sentences = ["aaa", "bbb", "ccc", "ddd"]
    chunks = imp._group_chunks(
        sentences, [1.0, 1.0, 1.0], threshold=0.5, min_chunk_chars=0, max_chunk_chars=7
    )
    assert chunks == ["aaa bbb", "ccc ddd"]


def test_adjacent_similarities_of_orthogonal_vectors(tmp_path):
    imp = indexer.Indexer(tmp_path)
    similarities = imp._adjacent_similarities(
        [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
    )
    assert similarities.shape == (2,)
    assert abs(float(similarities[0])) < 1e-6
    assert abs(float(similarities[1])) < 1e-6


def test_chunks_produces_semantic_chunks(tmp_path):
    imp = indexer.Indexer(tmp_path, embedding_function=OrthogonalEmbedding())
    text = "The quick brown fox. Jumps over the lazy dog."
    chunks = imp._chunks(text)
    assert len(chunks) == 1
    assert chunks[0] == "The quick brown fox. Jumps over the lazy dog."


def test_chunks_falls_back_to_structural_when_embedding_fails(tmp_path):
    def broken_embedding(texts):
        raise RuntimeError("no model")

    imp = indexer.Indexer(tmp_path, embedding_function=broken_embedding)
    text = "# Notes\n\nFirst paragraph here.\n\nSecond paragraph continues.\n\n## More\nDetails."
    chunks = imp._chunks(text)
    assert len(chunks) > 1
    assert chunks[0].startswith("# Notes")


def test_documents_skip_excluded_directories(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "keep.md").write_text("hello")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "skip.md").write_text("secret")
    imp = indexer.Indexer(tmp_path, excluded_dirs=(Path("private"),))
    documents = imp._documents()
    assert [doc_id for doc_id, _, _ in documents] == ["public/keep.md"]
