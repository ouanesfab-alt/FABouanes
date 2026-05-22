from __future__ import annotations

import pytest
from app.repositories.settings_repository import get_backup_dir, save_backup_dir
from app.core.db_access import execute_db


@pytest.fixture(autouse=True)
def clean_backup_setting():
    # Clean setting value before and after test
    execute_db("DELETE FROM app_settings WHERE key = 'gdrive_backup_dir'")
    yield
    execute_db("DELETE FROM app_settings WHERE key = 'gdrive_backup_dir'")


def test_get_backup_dir_default():
    # Default is empty string if not set
    assert get_backup_dir() == ""


def test_save_and_get_backup_dir():
    path = "/path/to/backup/dir"
    save_backup_dir(path)
    assert get_backup_dir() == path
