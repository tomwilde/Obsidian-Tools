from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import mcp
from tools import common


@mcp.tool()
async def list_files(path: str = "", extension: str | None = None) -> list[str]:
    """List the files at the given path relative to the vault root, optionally filtered by extension."""
    return _list_files(common.rootdir, path, extension)


@common.tool_generic_error_handler()
def _list_files(root: Path, relative: str, extension: str | None = None) -> list[str]:
    target = common.resolve_vault_path(root, relative)
    if not target.is_dir():
        raise ToolError(f"Not a directory: {relative}")
    files = sorted(
        item.name
        for item in target.iterdir()
        if item.is_file() and not common.is_excluded_path(root, item)
    )
    if extension is None:
        return files
    suffix = f".{extension.lstrip('.').lower()}"
    return [name for name in files if name.lower().endswith(suffix)]


@mcp.tool()
async def read_file(path: str) -> str:
    """Read the file at the given path relative to the vault root."""
    return _read_file(common.rootdir, path)


@common.tool_generic_error_handler()
def _read_file(root: Path, relative: str) -> str:
    target = common.resolve_vault_path(root, relative)
    if not target.is_file():
        raise ToolError("404 Not Found")
    return target.read_text(encoding="utf-8")
