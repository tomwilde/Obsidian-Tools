from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from config import determine_root_dir


rootdir = determine_root_dir()

mcp = MCPServer("obsidian")

@mcp.tool()
async def list_folders(path: str) -> list[str]:
    """List the directories at the given path relative to the vault root."""
    if path in (".", ".."):
        raise ToolError("403 Forbidden")
    return _list_folders(rootdir, path)

def _list_folders(root: Path, relative: str) -> list[str]:
    try:
        target = (root / relative).resolve()
        if not target.is_dir():
            raise ToolError(f"Not a directory: {relative}")
        return sorted(item.name for item in target.iterdir() if item.is_dir())
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Failed to list folders for {relative!r}: {exc}") from exc

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield

app = FastAPI(title="Obsidian MCP Server", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Welcome to the Obsidian MCP Server"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.mount("/", mcp.streamable_http_app())