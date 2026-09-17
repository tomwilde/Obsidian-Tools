from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import mcp
from tools import common


@mcp.tool()
async def list_files(path: str) -> list[str]:
    """List the files at the given path relative to the vault root."""
    common.guard_dot_paths(path)
    return _list_files(common.rootdir, path)


@common.tool_generic_error_handler()
def _list_files(root: Path, relative: str) -> list[str]:
    target = (root / relative).resolve()
    if not target.is_dir():
        raise ToolError(f"Not a directory: {relative}")
    return sorted(item.name for item in target.iterdir() if item.is_file())


@mcp.tool()
async def read_file(path: str) -> str:
    """Read the file at the given path relative to the vault root."""
    common.guard_dot_paths(path)
    return _read_file(common.rootdir, path)


@common.tool_generic_error_handler()
def _read_file(root: Path, relative: str) -> str:
    target = (root / relative).resolve()
    if not target.is_file():
        raise ToolError("404 Not Found")
    return target.read_text(encoding="utf-8")