from pathlib import Path
import os
import sys


def data_root() -> Path:
    override = os.environ.get('MOBILE_DESK_DATA')
    return Path(override).expanduser().resolve() if override else Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'MobileDesk'


def resource_path(name: str) -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'resources' / name


def prepare(root: Path) -> None:
    for part in ('data', 'backups', 'logs'):
        (root / part).mkdir(parents=True, exist_ok=True)
