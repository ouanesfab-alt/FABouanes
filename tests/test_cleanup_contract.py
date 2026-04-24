from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from fabouanes.postgres_support import SQLITE_IMPORT_FILE_NAME, detect_sqlite_import_source


class CleanupContractTests(unittest.TestCase):
    def _create_sqlite_users_db(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        try:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL)")
            conn.execute("INSERT INTO users (username) VALUES ('admin')")
            conn.commit()
        finally:
            conn.close()

    def test_project_no_longer_ships_root_sqlite_database(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self.assertFalse((project_root / "database.db").exists())

    def test_startup_scripts_define_fastapi_network_host_port(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        run_prod_text = (project_root / "run_prod.py").read_text(encoding="utf-8")
        launcher_text = (project_root / "DOUBLE_CLIC_LANCER_TOUT.bat").read_text(encoding="utf-8")
        reset_text = (project_root / "RESET_ADMIN_SECOURS.bat").read_text(encoding="utf-8")
        start_pg_text = (project_root / "START_POSTGRES.bat").read_text(encoding="utf-8")
        stop_pg_text = (project_root / "STOP_POSTGRES.bat").read_text(encoding="utf-8")

        self.assertIn("FAB_HOST", run_prod_text)
        self.assertIn("FAB_PORT", run_prod_text)
        self.assertIn('set "FAB_HOST=0.0.0.0"', launcher_text)
        self.assertIn('set "FAB_PORT=5000"', launcher_text)
        self.assertIn("run_prod.py", launcher_text)
        self.assertNotIn("reset_admin_password.py 0000 admin", launcher_text)
        self.assertIn("reset_admin_password.py", reset_text)
        self.assertIn("docker", start_pg_text.lower())
        self.assertIn("docker", stop_pg_text.lower())

    def test_project_no_longer_keeps_flask_shim_or_wsgi_entrypoint(self) -> None:
        project_root = Path(__file__).resolve().parents[1]

        self.assertFalse((project_root / "flask.py").exists())
        self.assertFalse((project_root / "wsgi.py").exists())
        self.assertFalse((project_root / "launcher.py").exists())

    def test_project_sources_no_longer_reference_flask_wsgi_or_gunicorn(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        source_files = [
            project_root / "app.py",
            project_root / "run_prod.py",
            project_root / "asgi.py",
            project_root / "deploy" / "docker" / "Dockerfile",
            project_root / "deploy" / "docker" / "docker-compose.yml",
        ]
        source_files.extend((project_root / "fabouanes").rglob("*.py"))

        for source_file in source_files:
            text = source_file.read_text(encoding="utf-8")
            self.assertNotIn("from flask import", text, source_file.as_posix())
            self.assertNotIn("ProxyFix", text, source_file.as_posix())
            self.assertNotIn("wsgi:app", text, source_file.as_posix())
            self.assertNotIn("gunicorn", text, source_file.as_posix())

    def test_detect_sqlite_import_source_prefers_local_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            app_data_dir = root / "appdata"
            base_dir = root / "project"
            base_source = base_dir / SQLITE_IMPORT_FILE_NAME
            local_source = app_data_dir / SQLITE_IMPORT_FILE_NAME

            self._create_sqlite_users_db(base_source)
            self.assertEqual(detect_sqlite_import_source(app_data_dir, base_dir), base_source)

            self._create_sqlite_users_db(local_source)
            self.assertEqual(detect_sqlite_import_source(app_data_dir, base_dir), local_source)

    def test_gitignore_protects_runtime_artifacts_and_env(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        gitignore_text = (project_root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".venv/", gitignore_text)
        self.assertIn(".env", gitignore_text)
        self.assertIn("!.env.example", gitignore_text)
