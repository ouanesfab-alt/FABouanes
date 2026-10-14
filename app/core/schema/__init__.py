"""
Responsibility: Backward-compatible seed functions and initial database configuration.
The canonical data access and migration implementation is in `app.core.database`.
"""

from __future__ import annotations

import os
import sys

from app.core.config import (  # noqa: F401
    APP_DATA_DIR,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
)
from app.core.database import (  # noqa: F401
    FIRST_ADMIN_PASSWORD_FILE,
    OTHER_OPERATION_NAME,
    OTHER_OPERATION_UNIT,
    _exec,
    _seed_default_admin as _db_seed_default_admin,
    _seed_default_settings,
    _seed_other_operation,
    bootstrap_and_migrate,
    seed_default_data,
)
from app.core.runtime_paths import ensure_runtime_dirs  # noqa: F401


def initial_admin_password() -> str:
    module = sys.modules.get(__name__)
    configured = str(getattr(module, "DEFAULT_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD) or "").strip()
    allow_insecure = os.environ.get("FAB_ALLOW_INSECURE_DEFAULT_ADMIN", "0").strip() == "1"
    if configured and (configured != "1234" or allow_insecure):
        return configured
    file_path = getattr(module, "FIRST_ADMIN_PASSWORD_FILE", FIRST_ADMIN_PASSWORD_FILE)
    if hasattr(file_path, "exists") and file_path.exists():
        try:
            for line in file_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("PIN="):
                    value = line.split("=", 1)[1].strip()
                    if value:
                        return value
        except Exception:
            pass
    pin = "7508"
    ensure_fn = getattr(module, "ensure_runtime_dirs", ensure_runtime_dirs)
    ensure_fn()
    if hasattr(file_path, "write_text"):
        file_path.write_text(
            f"Utilisateur={DEFAULT_ADMIN_USERNAME}\nPIN={pin}\n",
            encoding="utf-8",
        )
    return pin


def _seed_default_admin(conn) -> None:
    from app.core.config import settings

    module = sys.modules.get(__name__)
    pwd_val = getattr(module, "DEFAULT_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    if (
        str(pwd_val or "").strip().lower() == "admin"
        and settings.env == "production"
        and not settings.desktop_mode
    ):
        raise RuntimeError(
            "DEFAULT_ADMIN_PASSWORD cannot be 'admin' in production server mode. Set a strong password in your .env file."
        )
    _db_seed_default_admin(conn)


def init_db() -> None:
    """Delegates to database bootstrap and migrations."""
    bootstrap_and_migrate()


__all__ = [
    "DEFAULT_ADMIN_PASSWORD",
    "FIRST_ADMIN_PASSWORD_FILE",
    "OTHER_OPERATION_NAME",
    "OTHER_OPERATION_UNIT",
    "ensure_runtime_dirs",
    "initial_admin_password",
    "_exec",
    "_seed_default_settings",
    "_seed_default_admin",
    "_seed_other_operation",
    "seed_default_data",
    "init_db",
]

