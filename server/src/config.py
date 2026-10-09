import configparser
import os
import re
from pathlib import Path
from pathlib import PurePosixPath

CONFIG_FILE = Path(__file__).resolve().parent / "config.ini"
VAULT_DIR_ENV = "VAULT_DIR"
EXCLUDED_DIRS_ENV = "EXCLUDED_DIRS"
INCLUDED_FILETYPES_ENV = "INCLUDED_FILETYPES"
EXCLUDED_DIRS_OPTION = "ExcludedDirs"
DEFAULT_INCLUDED_FILETYPES = ("md",)


def load_config(config_file: Path = CONFIG_FILE) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if not parser.read(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    return parser


def determine_root_dir(config_file: Path = CONFIG_FILE) -> Path:
    env_root_dir = os.environ.get(VAULT_DIR_ENV)
    if env_root_dir:
        return Path(env_root_dir).expanduser()
    return Path(load_config(config_file)["Obsidian"]["RootDir"])


def determine_excluded_dirs(config_file: Path = CONFIG_FILE) -> tuple[Path, ...]:
    env_excluded_dirs = os.environ.get(EXCLUDED_DIRS_ENV)
    if env_excluded_dirs is not None:
        return _parse_excluded_dirs(env_excluded_dirs)
    parser = load_config(config_file)
    raw = parser["Obsidian"].get(EXCLUDED_DIRS_OPTION, "")
    return _parse_excluded_dirs(raw)


def determine_included_filetypes() -> tuple[str, ...]:
    raw = os.environ.get(INCLUDED_FILETYPES_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_INCLUDED_FILETYPES
    return _parse_included_filetypes(raw)


def _parse_excluded_dirs(raw: str) -> tuple[Path, ...]:
    paths: list[Path] = []
    seen: set[str] = set()
    for token in re.split(r"[\n,]", raw):
        entry = token.strip()
        if not entry:
            continue
        normalized = _normalize_relative_dir(entry)
        key = normalized.as_posix()
        if key in seen:
            continue
        seen.add(key)
        paths.append(normalized)
    return tuple(paths)


def _parse_included_filetypes(raw: str) -> tuple[str, ...]:
    filetypes: list[str] = []
    seen: set[str] = set()
    for token in re.split(r"[\n,]", raw):
        entry = token.strip().lstrip(".").lower()
        if not entry:
            continue
        if entry in seen:
            continue
        seen.add(entry)
        filetypes.append(entry)
    if not filetypes:
        return DEFAULT_INCLUDED_FILETYPES
    return tuple(filetypes)


def _normalize_relative_dir(raw: str) -> Path:
    value = raw.replace("\\", "/").strip()
    posix = PurePosixPath(value)
    if posix.is_absolute():
        posix = PurePosixPath(*posix.parts[1:])
    if not posix.parts:
        raise ValueError(f"Invalid excluded directory: {raw}")
    if any(part in ("", ".", "..") for part in posix.parts):
        raise ValueError(f"Invalid excluded directory: {raw}")
    return Path(posix.as_posix())
