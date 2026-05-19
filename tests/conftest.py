from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from werkzeug.security import generate_password_hash

try:
    import pg8000
except Exception:  # pragma: no cover - optional integration dependency
    pg8000 = None


TEST_ROOT = Path(__file__).resolve().parent / "_runtime_fastapi"
TEST_DATA_DIR = TEST_ROOT / "data"
USE_POSTGRES = True
PG_PORT = int(os.environ.get("FAB_TEST_PG_PORT", "55432"))
PG_DB = os.environ.get("FAB_TEST_PG_DB", "fabouanes_test")
PG_USER = os.environ.get("FAB_TEST_PG_USER", "fabouanes")
PG_PASSWORD = os.environ.get("FAB_TEST_PG_PASSWORD", "")
PGDATA_DIR = TEST_ROOT / "pgdata"
PG_LOG = TEST_ROOT / "postgres.log"
DATABASE_URL = (
    f"postgresql://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{PG_PORT}/{PG_DB}"
    if PG_PASSWORD
    else f"postgresql://{PG_USER}@127.0.0.1:{PG_PORT}/{PG_DB}"
)

os.environ["FAB_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["FAB_DISABLE_BACKGROUND_JOBS"] = "1"
os.environ["FAB_DESKTOP"] = "0"
os.environ["SECRET_KEY"] = "test-fastapi-secret"
os.environ["FASTAPI_ENV"] = "test"
os.environ["DATABASE_URL"] = DATABASE_URL


def _run(command: list[str], *, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, capture_output=True, text=True, timeout=timeout)


def _find_pg_binary(executable: str) -> str:
    override = os.environ.get("FAB_TEST_PG_BIN")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override) / executable)
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    for major in range(18, 9, -1):
        candidates.append(program_files / "PostgreSQL" / str(major) / "bin" / executable)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError(f"PostgreSQL binary not found: {executable}")


def _pg8000_connect(database: str):
    if pg8000 is None:
        raise RuntimeError("pg8000 is required when FAB_TEST_DB=postgres.")
    return pg8000.connect(user=PG_USER, password=PG_PASSWORD or None, host="127.0.0.1", port=PG_PORT, database=database)


def _ensure_postgres_cluster() -> None:
    initdb = _find_pg_binary("initdb.exe")
    pg_ctl = _find_pg_binary("pg_ctl.exe")
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    if PGDATA_DIR.exists() and not (PGDATA_DIR / "PG_VERSION").exists():
        shutil.rmtree(PGDATA_DIR, ignore_errors=True)
    if not PGDATA_DIR.exists():
        _run([initdb, "-D", str(PGDATA_DIR), "-U", PG_USER, "-A", "trust", "-E", "UTF8"])
    subprocess.Popen(
        [pg_ctl, "-D", str(PGDATA_DIR), "-l", str(PG_LOG), "-o", f"-p {PG_PORT} -h 127.0.0.1", "start"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            conn = _pg8000_connect("postgres")
            conn.close()
            admin_conn = _pg8000_connect("postgres")
            try:
                admin_conn.autocommit = True
                cursor = admin_conn.cursor()
                exists = False
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PG_DB,))
                exists = cursor.fetchone() is not None
                if not exists:
                    cursor.execute(f'CREATE DATABASE "{PG_DB}"')
            finally:
                admin_conn.close()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Temporary PostgreSQL test cluster did not become ready.")


def _stop_postgres_cluster() -> None:
    if not PGDATA_DIR.exists():
        return
    try:
        pg_ctl = _find_pg_binary("pg_ctl.exe")
        _run([pg_ctl, "-D", str(PGDATA_DIR), "-m", "fast", "-w", "stop"], check=False, timeout=20)
    except Exception:
        pass


def _reset_database() -> None:
    conn = _pg8000_connect(PG_DB)
    try:
        cursor = conn.cursor()
        cursor.execute("DROP SCHEMA IF EXISTS public CASCADE")
        cursor.execute("CREATE SCHEMA public")
        cursor.execute(f'GRANT ALL ON SCHEMA public TO "{PG_USER}"')
        cursor.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
        conn.commit()
    finally:
        conn.close()


_ensure_postgres_cluster()

from app.core.database import bootstrap_and_migrate  # noqa: E402
from app.main import app  # noqa: E402
from app.core.db_access import execute_db, query_db  # noqa: E402
from app.core.security import _rl_store  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def clean_runtime():
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _reset_database()
    bootstrap_and_migrate()
    yield
    _stop_postgres_cluster()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_rate_limit_store():
    _rl_store.clear()
    yield
    _rl_store.clear()


@pytest.fixture(autouse=True)
def ensure_admin_user(client: TestClient):
    execute_db(
        """
        INSERT INTO users (username, password_hash, role, must_change_password, is_active, last_password_change_at)
        VALUES (%s, %s, %s, FALSE, TRUE, CURRENT_TIMESTAMP)
        ON CONFLICT(username) DO UPDATE SET
            password_hash = excluded.password_hash,
            role = excluded.role,
            must_change_password = FALSE,
            is_active = TRUE,
            last_password_change_at = CURRENT_TIMESTAMP
        """,
        ("admin", generate_password_hash("1234"), "admin"),
    )
    if query_db("SELECT id FROM clients ORDER BY id LIMIT 1", one=True) is None:
        execute_db(
            "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)",
            ("Client Test", "0550000000", "Adresse Test", "", 0),
        )
    if query_db("SELECT id FROM suppliers ORDER BY id LIMIT 1", one=True) is None:
        execute_db(
            "INSERT INTO suppliers (name, phone, address, notes) VALUES (%s, %s, %s, %s)",
            ("Fournisseur Test", "0660000000", "Adresse Fournisseur", ""),
        )
    if query_db("SELECT id FROM raw_materials ORDER BY id LIMIT 1", one=True) is None:
        execute_db(
            "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES (%s, %s, %s, %s, %s, %s)",
            ("Matiere Test", "kg", 120, 50, 65, 10),
        )
    if query_db("SELECT id FROM finished_products ORDER BY id LIMIT 1", one=True) is None:
        execute_db(
            "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (%s, %s, %s, %s, %s)",
            ("Produit Test", "kg", 80, 120, 90),
        )
    if query_db("SELECT id FROM purchases ORDER BY id LIMIT 1", one=True) is None:
        supplier_id = int(query_db("SELECT id FROM suppliers ORDER BY id LIMIT 1", one=True)["id"])
        raw_material_id = int(query_db("SELECT id FROM raw_materials ORDER BY id LIMIT 1", one=True)["id"])
        execute_db(
            """
            INSERT INTO purchases (supplier_id, raw_material_id, quantity, unit, unit_price, total, purchase_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (supplier_id, raw_material_id, 12, "kg", 75, 900, "2026-04-17", "Achat test"),
        )


def extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf token not found"
    return match.group(1)


@pytest.fixture()
def logged_client(client: TestClient):
    response = client.get("/login")
    csrf_token = extract_csrf(response.text)
    post = client.post(
        "/login",
        data={"username": "admin", "password": "1234", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert post.status_code == 303
    yield client


@pytest.fixture()
def first_client_id():
    row = query_db("SELECT id FROM clients ORDER BY id LIMIT 1", one=True)
    assert row is not None
    return int(row["id"])


@pytest.fixture()
def first_supplier_id():
    row = query_db("SELECT id FROM suppliers ORDER BY id LIMIT 1", one=True)
    assert row is not None
    return int(row["id"])


@pytest.fixture()
def first_raw_material_id():
    row = query_db("SELECT id FROM raw_materials ORDER BY id LIMIT 1", one=True)
    assert row is not None
    return int(row["id"])


@pytest.fixture()
def first_product_id():
    row = query_db("SELECT id FROM finished_products ORDER BY id LIMIT 1", one=True)
    assert row is not None
    return int(row["id"])


@pytest.fixture()
def first_purchase_id():
    row = query_db("SELECT id FROM purchases ORDER BY id LIMIT 1", one=True)
    assert row is not None
    return int(row["id"])


@pytest.fixture()
def api_tokens(client: TestClient):
    # Log in as admin via the API login endpoint
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "1234"})
    assert response.status_code == 200
    data = response.json()["data"]
    return data["access_token"], data["refresh_token"]


@pytest.fixture()
def api_headers(api_tokens):
    access_token, _ = api_tokens
    return {"Authorization": f"Bearer {access_token}"}
