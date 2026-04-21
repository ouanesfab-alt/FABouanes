from __future__ import annotations

from fabouanes.core.db_access import get_setting, set_setting


def get_backup_dir() -> str:
    return get_setting('gdrive_backup_dir', '')


def save_backup_dir(value: str) -> None:
    set_setting('gdrive_backup_dir', value)
