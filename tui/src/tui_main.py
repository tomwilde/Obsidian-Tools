from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_module_path = Path(__file__).with_name("main.py")
_spec = spec_from_file_location("obsidian_tui_main", _module_path)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Unable to load TUI app module: {_module_path}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

ObsidianTui = _module.ObsidianTui

__all__ = ["ObsidianTui"]
