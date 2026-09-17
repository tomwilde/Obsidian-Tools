import functools
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from config import determine_root_dir


rootdir = determine_root_dir()

mcp = MCPServer("obsidian")

def _guard_dot_paths(path: str) -> None:
    if path in (".", ".."):
        raise ToolError("403 Forbidden")

def _tool_generic_error_handler() -> Callable[[Callable[..., list[str]]], Callable[..., list[str]]]:
    def decorator(func: Callable[..., list[str]]) -> Callable[..., list[str]]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> list[str]:
            try:
                return func(*args, **kwargs)
            except ToolError:
                raise
            except Exception as exc:
                raise ToolError(f"General error: {exc}") from exc
        return wrapper
    return decorator

@mcp.tool()
async def list_folders(path: str) -> list[str]:
    """List the directories at the given path relative to the vault root."""
    _guard_dot_paths(path)
    return _list_folders(rootdir, path)

@_tool_generic_error_handler()
def _list_folders(root: Path, relative: str) -> list[str]:
    target = (root / relative).resolve()
    if not target.is_dir():
        raise ToolError(f"Not a directory: {relative}")
    return sorted(item.name for item in target.iterdir() if item.is_dir())

@mcp.tool()
async def list_files(path: str) -> list[str]:
    """List the files at the given path relative to the vault root."""
    _guard_dot_paths(path)
    return _list_files(rootdir, path)

@_tool_generic_error_handler()
def _list_files(root: Path, relative: str) -> list[str]:
    target = (root / relative).resolve()
    if not target.is_dir():
        raise ToolError(f"Not a directory: {relative}")
    return sorted(item.name for item in target.iterdir() if item.is_file())

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