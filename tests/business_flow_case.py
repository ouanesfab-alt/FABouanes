from __future__ import annotations

import html
import os
import shutil
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

TEST_ROOT = Path(__file__).resolve().parent / "_runtime"
os.environ["FAB_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["LOCALAPPDATA"] = str(TEST_ROOT / "localappdata")
os.environ["DATABASE_URL"] = ""
os.environ["SESSION_COOKIE_SECURE"] = "0"

from app import app, ensure_runtime_dirs, init_db
from fabouanes import security
from fabouanes.db import connect_database
from fabouanes.runtime_app import DB_PATH, REPORTLAB_AVAILABLE


TEST_ADMIN_PASSWORD = "AdminTest!123"
TEST_MANAGER_PASSWORD = "ManagerTest!123"
TEST_OPERATOR_PASSWORD = "OperatorTest!123"


class BusinessFlowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        self._reset_runtime()
        init_db()
        security._rl_store.clear()
        self.client = app.test_client()
        self._set_admin_password()

    def _reset_runtime(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH.touch()
        ensure_runtime_dirs()

    def _connection(self):
        return connect_database("", DB_PATH)

    def _execute(self, query: str, params: tuple = ()) -> int | None:
        conn = self._connection()
        try:
            cur = conn.execute(query, params)
            lastrowid = cur.lastrowid
            cur.close()
            conn.commit()
            return lastrowid
        finally:
            conn.close()

    def _fetchone(self, query: str, params: tuple = ()):
        conn = self._connection()
        try:
            cur = conn.execute(query, params)
            row = cur.fetchone()
            cur.close()
            return row
        finally:
            conn.close()

    def _scalar(self, query: str, params: tuple = ()) -> float | int | str | None:
        row = self._fetchone(query, params)
        if row is None:
            return None
        return row[0]

    def _set_admin_password(self) -> None:
        self._execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE username = ?",
            (generate_password_hash(TEST_ADMIN_PASSWORD), "admin"),
        )

    def _create_user(self, username: str, password: str, role: str = "operator", is_active: int = 1) -> int:
        return int(
            self._execute(
                """
                INSERT INTO users (username, password_hash, role, must_change_password, is_active, last_password_change_at)
                VALUES (?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
                """,
                (username, generate_password_hash(password), role, is_active),
            )
        )

    def _create_supplier(self, name: str = "Fournisseur Test") -> int:
        return int(
            self._execute(
                "INSERT INTO suppliers (name, phone, address, notes) VALUES (?, ?, ?, ?)",
                (name, "", "", ""),
            )
        )

    def _create_client(self, name: str = "Client Test") -> int:
        return int(
            self._execute(
                "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (?, ?, ?, ?, ?)",
                (name, "", "", "", 0),
            )
        )

    def _create_raw_material(
        self,
        name: str = "Semoule",
        unit: str = "kg",
        stock_qty: float = 0,
        avg_cost: float = 0,
        sale_price: float = 0,
    ) -> int:
        return int(
            self._execute(
                "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, unit, stock_qty, avg_cost, sale_price, 0, 0),
            )
        )

    def _create_finished_product(
        self,
        name: str = "Produit Test",
        default_unit: str = "kg",
        stock_qty: float = 0,
        sale_price: float = 0,
        avg_cost: float = 0,
    ) -> int:
        return int(
            self._execute(
                "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (?, ?, ?, ?, ?)",
                (name, default_unit, stock_qty, sale_price, avg_cost),
            )
        )

    def _csrf_token(self, path: str) -> str:
        response = self.client.get(path)
        self.assertLess(response.status_code, 500)
        with self.client.session_transaction() as sess:
            return str(sess["csrf_token"])

    def _post_form(self, path: str, data: dict[str, object], preflight_path: str, follow_redirects: bool = True):
        payload = dict(data)
        payload["csrf_token"] = self._csrf_token(preflight_path)
        return self.client.post(path, data=payload, follow_redirects=follow_redirects)

    def _login(self) -> None:
        self._login_as("admin", TEST_ADMIN_PASSWORD)

    def _login_as(self, username: str, password: str) -> None:
        response = self._post_form(
            "/login",
            {"username": username, "password": password},
            preflight_path="/login",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertIn("user_id", sess)

    def _api_login(self, username: str, password: str) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("data", payload)
        return payload["data"]

