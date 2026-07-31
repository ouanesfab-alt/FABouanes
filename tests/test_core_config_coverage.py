"""Tests complets pour app/core/config.py (Vague 1.1 — couverture > 90%)."""
from __future__ import annotations

import os
from unittest import mock
import pytest

from app.core.config import (
    Settings,
    _default_data_dir,
    _ensure_env_file_exists,
    configured_worker_count,
    validate_single_worker_runtime,
)


def test_default_data_dir_explicit(tmp_path):
    with mock.patch.dict(os.environ, {"FAB_DATA_DIR": str(tmp_path / "explicit")}):
        d = _default_data_dir()
        assert str(d) == str(tmp_path / "explicit")


def test_default_data_dir_localappdata(tmp_path):
    with mock.patch.dict(os.environ, {"FAB_DATA_DIR": "", "LOCALAPPDATA": str(tmp_path / "local")}):
        d = _default_data_dir()
        assert "local" in str(d)


def test_default_data_dir_posix_xdg(tmp_path):
    with mock.patch.dict(os.environ, {"FAB_DATA_DIR": "", "LOCALAPPDATA": "", "XDG_DATA_HOME": str(tmp_path / "xdg")}):
        d = _default_data_dir()
        assert d is not None












def test_ensure_env_file_exists_copy_example(tmp_path):
    base_dir = tmp_path / "app_base"
    base_dir.mkdir()
    (base_dir / ".env.example").write_text("FOO=BAR\n", encoding="utf-8")

    with mock.patch("app.core.config.BASE_DIR", base_dir):
        _ensure_env_file_exists()
        assert (base_dir / ".env").exists()
        assert "FOO=BAR" in (base_dir / ".env").read_text(encoding="utf-8")


def test_ensure_env_file_exists_create_default(tmp_path):
    base_dir = tmp_path / "app_base_empty"
    base_dir.mkdir()

    with mock.patch("app.core.config.BASE_DIR", base_dir):
        _ensure_env_file_exists()
        assert (base_dir / ".env").exists()
        assert "DATABASE_URL" in (base_dir / ".env").read_text(encoding="utf-8")


def test_settings_secret_key_from_file(tmp_path):
    app_data = tmp_path / "app_data"
    app_data.mkdir()
    (app_data / "secret.key").write_text("secret_from_file_12345", encoding="utf-8")

    s = Settings(app_data_dir=app_data, secret_key="")
    assert s.secret_key == "secret_from_file_12345"


def test_settings_secret_key_auto_generated(tmp_path):
    app_data = tmp_path / "app_data_gen"
    app_data.mkdir()

    s = Settings(app_data_dir=app_data, secret_key="")
    assert len(s.secret_key) > 10
    assert (app_data / "secret.key").exists()


def test_settings_missing_secret_key_raises_runtime_error(tmp_path):
    app_data = tmp_path / "app_data_err"
    app_data.mkdir()

    with mock.patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "", "FAB_TESTING": "0"}), \
         mock.patch("pathlib.Path.write_text", side_effect=OSError("Permission denied")):
        with pytest.raises(RuntimeError, match="SECRET_KEY est obligatoire"):
            Settings(app_data_dir=app_data, secret_key="")


def test_settings_invalid_admin_password_raises(tmp_path):
    with pytest.raises(RuntimeError, match="DEFAULT_ADMIN_PASSWORD cannot be 'admin'"):
        Settings(
            app_data_dir=tmp_path,
            env="production",
            desktop_mode=False,
            default_admin_password="admin",
            secret_key="some_key"
        )


def test_settings_cookie_secure_https_toggle(tmp_path):
    with mock.patch.dict(os.environ, {"SESSION_COOKIE_SECURE": "1"}):
        s = Settings(app_data_dir=tmp_path, env="production", desktop_mode=False, secret_key="k")
        assert s.session_cookie_secure is True

    with mock.patch.dict(os.environ, {"SESSION_COOKIE_SECURE": "0", "FAB_HTTPS": "0"}):
        s = Settings(app_data_dir=tmp_path, env="production", desktop_mode=False, secret_key="k")
        assert s.session_cookie_secure is False


def test_database_url_validation():
    s = Settings(secret_key="key")
    with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://postgres:pass@localhost:5432/db"}):
        assert s.database_url == "postgresql://postgres:pass@localhost:5432/db"

    with mock.patch.dict(os.environ, {"DATABASE_URL": ""}):
        with pytest.raises(RuntimeError, match="DATABASE_URL doit etre specifie"):
            _ = s.database_url

    with mock.patch.dict(os.environ, {"DATABASE_URL": "mysql://user:pass@localhost/db"}):
        with pytest.raises(RuntimeError, match="Seul PostgreSQL est supporte"):
            _ = s.database_url


def test_configured_worker_count():
    with mock.patch.dict(os.environ, {"FAB_WORKERS": "4"}):
        assert configured_worker_count() == 4

    with mock.patch.dict(os.environ, {"FAB_WORKERS": "invalid", "WEB_CONCURRENCY": "2"}):
        assert configured_worker_count() == 2


def test_validate_single_worker_runtime():
    with mock.patch("app.core.config.configured_worker_count", return_value=1):
        validate_single_worker_runtime()

    with mock.patch("app.core.config.configured_worker_count", return_value=4), \
         mock.patch.dict(os.environ, {"FAB_ALLOW_MULTI_WORKER": "1"}):
        validate_single_worker_runtime()

    with mock.patch("app.core.config.configured_worker_count", return_value=4), \
         mock.patch.dict(os.environ, {"FAB_ALLOW_MULTI_WORKER": "0"}):
        with pytest.raises(RuntimeError, match="FABOuanes utilise un cache"):
            validate_single_worker_runtime()
