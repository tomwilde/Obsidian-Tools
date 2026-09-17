import functools
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver.exceptions import ToolError

from config import determine_root_dir

rootdir: Path = determine_root_dir()

T = TypeVar("T")


def guard_dot_paths(path: str) -> None:
    if path in (".", ".."):
        raise ToolError("403 Forbidden")


def tool_generic_error_handler() -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except ToolError:
                raise
            except Exception as exc:
                raise ToolError(f"General error: {exc}") from exc
        return wrapper
    return decorator