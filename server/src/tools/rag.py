from pathlib import Path
from typing import Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import mcp
from tools import common

RagStatus = Literal["NotIndexed", "Indexing", "Indexed"]
IndexingStatus = Literal["Indexing", "Indexed"]


class IndexFolder(TypedDict):
    folder: str
    status: IndexingStatus
    percent_done: int


class RagMatch(TypedDict):
    file: str
    text: str
    score: float


@mcp.tool()
async def rag_folder_status(path: str) -> RagStatus:
    """Get the RAG index status of the folder at the given path relative to the vault root."""
    common.guard_dot_paths(path)
    return _rag_folder_status(common.rootdir, path)


@common.tool_generic_error_handler()
def _rag_folder_status(root: Path, relative: str) -> RagStatus:
    target = (root / relative).resolve()
    if not target.is_dir():
        raise ToolError("404 Not Found")
    return "NotIndexed"


@mcp.tool()
async def rag_index_folder(path: str) -> int:
    """Index the folder at the given path relative to the vault root for RAG."""
    common.guard_dot_paths(path)
    return _rag_index_folder(common.rootdir, path)


@common.tool_generic_error_handler()
def _rag_index_folder(root: Path, relative: str) -> int:
    target = (root / relative).resolve()
    if not target.is_dir():
        raise ToolError("404 Not Found")
    return 200


@mcp.tool()
async def rag_list_index_folders() -> list[IndexFolder]:
    """List the folders being indexed for RAG with their status and progress."""
    return _rag_list_index_folders()


@common.tool_generic_error_handler()
def _rag_list_index_folders() -> list[IndexFolder]:
    return []


@mcp.tool()
async def rag_clear_index_folder(path: str) -> int:
    """Clear the RAG index for the folder at the given path relative to the vault root."""
    common.guard_dot_paths(path)
    return _rag_clear_index_folder(common.rootdir, path)


@common.tool_generic_error_handler()
def _rag_clear_index_folder(root: Path, relative: str) -> int:
    target = (root / relative).resolve()
    if not target.is_dir():
        raise ToolError("404 Not Found")
    return 200


@mcp.tool()
async def rag_clear_all_index_folders() -> int:
    """Clear all RAG indexes."""
    return _rag_clear_all_index_folders()


@common.tool_generic_error_handler()
def _rag_clear_all_index_folders() -> int:
    return 200


@mcp.tool()
async def rag_query(query_text: str) -> list[RagMatch]:
    """Run a text query across the vault using RAG."""
    return _rag_query(query_text)


@common.tool_generic_error_handler()
def _rag_query(query_text: str) -> list[RagMatch]:
    return []