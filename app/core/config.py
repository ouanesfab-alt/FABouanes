from __future__ import annotations

import os
import secrets as _secrets
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


APP_NAME = "FABOuanes"
BASE_DIR = Path(os.getenv("FAB_BASE_DIR", "").strip() or Path(__file__).resolve().parents[2])


def _default_data_dir() -> Path:
    explicit = os.getenv("FAB_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit)
    local = os.getenv("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / APP_NAME
    if os.name == "nt":
        return Path.home() / "AppData" / "Local" / APP_NAME
    xdg = os.getenv("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg) / APP_NAME
    return BASE_DIR / APP_NAME


APP_DATA_DIR = _default_data_dir()
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")
load_dotenv(APP_DATA_DIR / ".env", override=False)


@dataclass(slots=True)
class Settings:
    app_name: str = APP_NAME
    base_dir: Path = BASE_DIR
    app_data_dir: Path = APP_DATA_DIR
    env: str = os.getenv("FASTAPI_ENV", os.getenv("FLASK_ENV", "production")).lower()
    desktop_mode: bool = os.getenv("FAB_DESKTOP", "0") == "1"
    secret_key: str = os.getenv("SECRET_KEY", "").strip()
    session_cookie_secure: bool = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    default_admin_username: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_admin_password: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    host: str = os.getenv("FAB_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port: int = int(os.getenv("FAB_PORT", "5000") or "5000")
    session_max_age: int = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 12)))

    def __post_init__(self) -> None:
        if not self.secret_key:
            key_file = self.app_data_dir / "secret.key"
            if key_file.exists():
                try:
                    self.secret_key = key_file.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

        testing = os.getenv("PYTEST_CURRENT_TEST") or os.getenv("FAB_TESTING", "") == "1"
        if not self.secret_key:
            if not testing:
                raise RuntimeError(
                    "SECRET_KEY est obligatoire en production. "
                    "Generez-en un avec: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            self.secret_key = _secrets.token_hex(32)

        # Force secure session cookies in non-desktop production environments by default
        if self.env == "production" and not self.desktop_mode:
            if os.getenv("SESSION_COOKIE_SECURE") is None:
                self.session_cookie_secure = True

    @property
    def database_url(self) -> str:
        configured = os.getenv("DATABASE_URL", "").strip()
        if not configured:
            raise RuntimeError("DATABASE_URL doit etre specifie. PostgreSQL est obligatoire.")
        if not configured.lower().startswith(("postgres://", "postgresql://")):
            raise RuntimeError("Seul PostgreSQL est supporte. DATABASE_URL doit commencer par postgres:// ou postgresql://.")
        return configured

    @property
    def debug(self) -> bool:
        return self.env == "development"


def configured_worker_count() -> int:
    for name in ("FAB_WORKERS", "WEB_CONCURRENCY", "UVICORN_WORKERS", "GUNICORN_WORKERS"):
        raw = os.getenv(name, "").strip()
        if not raw:
            continue
        try:
            return max(1, int(raw))
        except ValueError:
            continue
    return 1


def validate_single_worker_runtime() -> None:
    workers = configured_worker_count()
    allow = os.getenv("FAB_ALLOW_MULTI_WORKER", "0").strip().lower() in {"1", "true", "yes", "on"}
    if workers > 1 and not allow:
        raise RuntimeError(
            "FABOuanes utilise un cache et un scheduler in-process: demarre 1 seul worker "
            "ou configure un cache/scheduler externe avant FAB_ALLOW_MULTI_WORKER=1."
        )


settings = Settings()

DATABASE_URL = settings.database_url
SESSION_COOKIE_SECURE = settings.session_cookie_secure
DEFAULT_ADMIN_USERNAME = settings.default_admin_username
DEFAULT_ADMIN_PASSWORD = settings.default_admin_password
ENV = settings.env
DEBUG = settings.debug
