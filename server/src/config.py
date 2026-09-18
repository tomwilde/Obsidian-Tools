import configparser
import os
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "config.ini"
VAULT_DIR_ENV = "VAULT_DIR"


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
