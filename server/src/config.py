import configparser
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "config.ini"


def load_config(config_file: Path = CONFIG_FILE) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if not parser.read(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    return parser


def determine_root_dir(config_file: Path = CONFIG_FILE) -> Path:
    return Path(load_config(config_file)["Obsidian"]["RootDir"])