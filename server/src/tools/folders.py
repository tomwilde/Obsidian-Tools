from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import mcp
from tools import common


@mcp.tool()
async def list_folders(path: str) -> list[str]:
    """List the directories at the given path relative to the vault root."""
    return _list_folders(common.rootdir, path)


@common.tool_generic_error_handler()
def _list_folders(root: Path, relative: str) -> list[str]:
    target = common.resolve_vault_path(root, relative)
    if not target.is_dir():
        raise ToolError(f"Not a directory: {relative}")
    return sorted(item.name for item in target.iterdir() if item.is_dir())
