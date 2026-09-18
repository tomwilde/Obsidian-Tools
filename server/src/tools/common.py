import functools
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver.exceptions import ToolError

from config import determine_root_dir

rootdir: Path = determine_root_dir()

T = TypeVar("T")


def resolve_vault_path(root: Path, relative: str) -> Path:
    """Resolve a user path to a concrete path within the vault root.

    Leading slashes are treated as vault-root anchors (not filesystem root).
    Dot-paths and traversal escapes are forbidden.
    """
    if relative in (".", ".."):
        raise ToolError("403 Forbidden")

    canonical_root = root.resolve()
    rel = (relative or "").replace("\\", "/").strip().lstrip("/")
    target = (canonical_root / rel).resolve()

    try:
        target.relative_to(canonical_root)
    except ValueError:
        raise ToolError("403 Forbidden") from None

    return target


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
    target = resolve_vault_path(rootdir, relative)
    inside = target.relative_to(rootdir.resolve())
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
