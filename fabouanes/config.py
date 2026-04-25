from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "FABOuanes"
BUNDLED_DB_PATH = BASE_DIR / "database.db"


def _default_data_dir() -> Path:
    explicit = os.getenv('FAB_DATA_DIR', '').strip()
    if explicit:
        return Path(explicit)
    local = os.getenv('LOCALAPPDATA', '').strip()
    if local:
        return Path(local) / APP_NAME
    xdg = os.getenv('XDG_DATA_HOME', '').strip()
    if xdg:
        return Path(xdg) / APP_NAME
    return BASE_DIR / APP_NAME


APP_DATA_DIR = _default_data_dir()
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / '.env')
load_dotenv(APP_DATA_DIR / '.env', override=False)

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', '1234')
ENV = os.getenv('FLASK_ENV', 'production').lower()
DEBUG = ENV == 'development'
