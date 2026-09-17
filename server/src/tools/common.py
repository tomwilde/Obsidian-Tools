import functools
from collections.abc import Callable
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from config import determine_root_dir

rootdir: Path = determine_root_dir()


def guard_dot_paths(path: str) -> None:
    if path in (".", ".."):
        raise ToolError("403 Forbidden")


def tool_generic_error_handler() -> Callable[[Callable[..., list[str]]], Callable[..., list[str]]]:
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