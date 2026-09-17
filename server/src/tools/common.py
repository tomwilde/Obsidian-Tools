import functools
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver.exceptions import ToolError

from config import determine_root_dir

rootdir: Path = determine_root_dir()

T = TypeVar("T")


def normalize_vault_relative(relative: str) -> str:
    """Map a vault path into a clean, forward-slash, root-anchored relative
    path that is guaranteed to stay inside the vault.

    Path forms accepted:
      ''            -> vault root ([''])
      '/'          -> vault root
      '/foo'       -> vault/foo
      '/foo/bar'   -> vault/foo/bar
      'foo', 'foo\\bar'  -> same (Windows separators tolerated)

    A leading '/' is an anchor to the Vault root, not the drive root. The
    literal dot-paths '.' and '..' are forbidden, and any traversal or drive
    escape ('../x', '..\\..\\x', absolute drive paths) raises 403.
    """
    if relative in (".", ".."):
        raise ToolError("403 Forbidden")
    rel = relative.replace("\\", "/").strip().lstrip("/")
    target = (rootdir / rel).resolve()
    try:
        inside = target.relative_to(rootdir)
    except ValueError:
        raise ToolError("403 Forbidden") from None
    return "" if inside == Path(".") else inside.as_posix()


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
