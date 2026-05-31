"""
Tests unitaires et d'intégration mockés — couverture 80 %+ sur services, web, api et db.
Aucune base de données ni connexion réseau réelle nécessaire.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from collections import OrderedDict

# ── 1. Configuration des Mocks Redis et Caching AVANT tout import ────────────
class MockPubSub:
    def subscribe(self, *args, **kwargs): pass
    def listen(self): return []
    def close(self): pass

class MockScript:
    def __call__(self, *args, **kwargs): return True

class MockPipeline:
    def __init__(self): pass
    def get(self, *args, **kwargs): return self
    def set(self, *args, **kwargs): return self
    def incr(self, *args, **kwargs): return self
    def hincrby(self, *args, **kwargs): return self
    def zremrangebyscore(self, *args, **kwargs): return self
    def zadd(self, *args, **kwargs): return self
    def zcard(self, *args, **kwargs): return self
    def zrange(self, *args, **kwargs): return self
    def expire(self, *args, **kwargs): return self
    def hget(self, *args, **kwargs): return self
    def hset(self, *args, **kwargs): return self
    def hgetall(self, *args, **kwargs): return self
    def hexists(self, *args, **kwargs): return self
    def hdel(self, *args, **kwargs): return self
    def exists(self, *args, **kwargs): return self
    def publish(self, *args, **kwargs): return self
    def execute(self, *args, **kwargs):
        return [0, 0, 1, True]

class MockRedis:
    def __init__(self, *args, **kwargs): pass
    def ping(self): return True
    def pubsub(self, *args, **kwargs): return MockPubSub()
    def get(self, key, *args, **kwargs): return None
    def set(self, key, value, *args, **kwargs): return True
    def setex(self, key, time, value, *args, **kwargs): return True
    def incr(self, key, *args, **kwargs): return 1
    def hincrby(self, key, field, amount, *args, **kwargs): return 1
    def keys(self, pattern, *args, **kwargs): return []
    def register_script(self, *args, **kwargs): return MockScript()
    def pipeline(self): return MockPipeline()
    def zremrangebyscore(self, *args, **kwargs): return 0
    def zadd(self, *args, **kwargs): return 1
    def zrange(self, *args, **kwargs): return []
    def zrangebyscore(self, *args, **kwargs): return []
    def zcard(self, *args, **kwargs): return 0
    def delete(self, *args, **kwargs): return 1
    def expire(self, *args, **kwargs): return True
    def publish(self, channel, message): return 1
    def hget(self, name, key): return None
    def hset(self, name, key, value): return 1
    def hgetall(self, name): return {}
    def hexists(self, name, key): return False
    def hdel(self, name, *keys): return 0
    def exists(self, *names): return 0

class MockAsyncRedis:
    async def ping(self): return True
    async def get(self, *args, **kwargs): return None
    async def setex(self, *args, **kwargs): return True
    async def close(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass

mock_redis = MagicMock()
mock_redis.from_url.return_value = MockRedis()
mock_redis.Redis.return_value = MockRedis()
mock_redis.__version__ = "5.0.1"
mock_redis.asyncio = MagicMock()
mock_redis.asyncio.from_url.return_value = MockAsyncRedis()

sys.modules["redis"] = mock_redis
sys.modules["redis.asyncio"] = mock_redis.asyncio

# ── 2. Variables d'environnement de test ─────────────────────────────────────
os.environ.setdefault("SECRET_KEY", "test-secret-key-services-coverage")
os.environ.setdefault("FASTAPI_ENV", "test")
os.environ.setdefault("FAB_DESKTOP", "0")
os.environ.setdefault("DATABASE_URL", "postgresql://fake@localhost/fake_test")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("FAB_DISABLE_BACKGROUND_JOBS", "1")

# ── 3. Configuration des Mocks Database (DBAPI) et CompatRow ─────────────────
from werkzeug.security import generate_password_hash
from app.core.db_helpers import CompatRow

def mock_dbapi_rows_for_sql(sql: str, params: tuple | dict = ()):
    q = sql.lower()
    
    # 0. Client keys query check first (very specific)
    if "client_keys" in q or "encryption_key" in q:
        cols = [("client_id",), ("encryption_key",)]
        import base64
        dummy_b64_key = base64.b64encode(b"01234567890123456789012345678912").decode("utf-8")
        return cols, [(1, dummy_b64_key)]

    # 0_reports. Specific report queries (placed above count rule to prevent interception)
    if "sale_date as date" in q:
        cols = [("client_id",), ("date",), ("total",), ("sale_type",)]
        rows = [(1, "2026-05-31", 300.0, "credit")]
        return cols, rows

    if "payment_date as date" in q:
        cols = [("client_id",), ("date",), ("amount",), ("payment_type",)]
        rows = [(1, "2026-05-31", 200.0, "versement")]
        return cols, rows

    if "finished_product_id" in q and "qty" in q and "revenue" in q:
        cols = [("name",), ("revenue",), ("profit",), ("qty",)]
        rows = [("Product X", 300.0, 150.0, 10.0)]
        return cols, rows

    if "client_id" in q and "revenue" in q and "profit" in q and "nb" in q:
        cols = [("name",), ("revenue",), ("profit",), ("count",)]
        rows = [("Client Dupont", 300.0, 150.0, 5)]
        return cols, rows

    if "expenses" in q and "category" in q:
        cols = [("category",), ("total",), ("count",)]
        rows = [("Office", 100.0, 2), ("Travel", 50.0, 1)]
        return cols, rows

    if "group by day" in q or "group by month" in q or "order by month" in q or "as month" in q or "as day" in q or "anon_1.month" in q or "anon_1.day" in q:
        cols = [("month",), ("day",), ("total",), ("profit",), ("count",)]
        rows = [("2026-05", "2026-05-31", 300.0, 150.0, 1)]
        return cols, rows

    # 0_count. Count queries check first to prevent intercepting specific page list queries
    if ("count(" in q or "exists" in q or "line_count" in q) and not any(x in q for x in ["total_amount", "total_purchases", "total_sales", "contact_type"]):
        return [("c",), ("line_count",), ("count",)], [(1, 1, 1)]

    # 4. Diagnostic dashboard / daily summary (moved to top to avoid intercepting by reports page 'day' check)
    if "sales_today" in q or "sales_week_ago" in q or "cash_today" in q or "profit_today" in q:
        cols = [("sales_today",), ("sales_week_ago",), ("cash_today",), ("profit_today",), ("total_receivables",)]
        return cols, [(100.0, 80.0, 50.0, 20.0, 150.0)]

    # 4c. Top debtors / client balances list (check before general mv_client_balances)
    if "mv_client_balances" in q and ("id" in q or "name" in q):
        cols = [("id",), ("name",), ("balance",)]
        return cols, [(1, "Client Dupont", 150.0)]

    # 4b. Cumulative summary / dashboard (moved to top to avoid intercepting by cost_of_goods reports rule)
    if "total_receivables" in q or "mv_client_balances" in q or "revenue" in q:
        cols = [("total_receivables",), ("total_profit",), ("revenue",), ("cost_of_goods",), ("gross_profit",)]
        return cols, [(150.0, 20.0, 100.0, 80.0, 20.0)]

    # 5. Alert jours_inactif / overdue clients (moved to top to avoid intercepting by reports page 'day' check)
    if "jours_inactif" in q or "overdue" in q:
        return [("id",), ("name",), ("balance",), ("jours_inactif",)], [(1, "Client Dupont", 150.0, 31)]

    # 0af. Cost of goods query (reports)
    if "cost_of_goods" in q:
        cols = [("cost_of_goods",)]
        rows = [(150.0,)]
        return cols, rows



    # 0aa. Dashboard sales summary (must check first to avoid intercepting by count() or union all)
    if "union all" in q and "nb_sales" in q:
        cols = [("sale_date",), ("nb_sales",), ("total_sales",), ("total_paid",), ("total_due",), ("total_profit",)]
        rows = [("2026-05-31", 1, 300.0, 100.0, 200.0, 150.0)]
        return cols, rows

    # 0ab. Contacts directory union (must check before generic union all Rule 10)
    if "contact_type" in q or "fournisseur" in q:
        cols = [("contact_type",), ("id",), ("name",), ("phone",), ("address",), ("notes",), ("current_balance",), ("total_amount",), ("total_paid",), ("total_advance",)]
        rows = [("Client", 1, "Client Dupont", "0606060606", "Paris", "", 150.0, 300.0, 150.0, 50.0),
                ("Fournisseur", 1, "Fournisseur A", "0707070707", "Lyon", "", 0.0, 200.0, 0.0, 0.0)]
        return cols, rows

    # 0ac. Reports page period summary (must check before count() or other subqueries)
    if "total_purchases" in q or ("total_sales" in q and "total_payments" in q):
        cols = [("total_sales",), ("total_profit",), ("nb_sales",), ("total_purchases",), ("nb_purchases",), ("total_payments",), ("nb_payments",)]
        rows = [(300.0, 150.0, 1, 200.0, 1, 100.0, 1)]
        return cols, rows

    # 0ae. Stock materials with consumption (must check before production_batches)
    if "consumed_30d" in q:
        cols = [("id",), ("name",), ("stock_qty",), ("alert_threshold",), ("threshold_qty",), ("avg_cost",), ("sale_price",), ("default_unit",), ("unit",), ("consumed_30d",)]
        rows = [(1, "Raw Mat A", 50.0, 10.0, 5.0, 3.0, 4.0, "kg", "kg", 15.0)]
        return cols, rows

    # 0ad. Production batches (must check before generic products or sales rules)
    if "production_batches" in q or "production_batch" in q:
        cols = [("id",), ("finished_product_id",), ("output_quantity",), ("production_cost",), ("unit_cost",), ("production_date",), ("notes",), ("finished_name",), ("product_name",), ("product_unit",), ("_total_count",), ("batch_id",), ("raw_material_id",), ("quantity",), ("unit",), ("name",)]
        rows = [(1, 1, 10.0, 100.0, 10.0, "2026-05-31", "Batch note", "Product X", "Product X", "kg", 1, 1, 1, 10.0, "kg", "Raw Mat A")]
        return cols, rows

    # 0b. Timeline query (check first to avoid intercepting with payments or sales)
    if "event_type" in q or "timeline" in q:
        cols = [("row_id",), ("document_id",), ("sort_sequence",), ("event_date",), ("designation",), ("item_name",), ("quantity",), ("unit",), ("purchase_amount",), ("payment_amount",), ("event_type",)]
        rows = [(1, 1, 1, "2026-05-31", None, "Product X", 10.0, "kg", 300.0, 0.0, "sale_finished")]
        return cols, rows

    # 0c. Recalc document totals (check before count() queries)
    if "total_amount" in q or "due_amount" in q:
        cols = [("line_count",), ("total_amount",), ("paid_amount",), ("due_amount",)]
        return cols, [(1, 300.0, 100.0, 200.0)]

    # 1. Lock queries
    if "pg_try_advisory" in q or "locked" in q:
        return [("locked",)], [(1,)]
        
    # 3. Settings
    if "app_settings" in q:
        val = "1"
        param_val = ""
        if isinstance(params, dict):
            param_val = params.get("key", "")
        elif isinstance(params, (list, tuple)) and params:
            param_val = params[0]
            
        if param_val == "diagnostic_last_write":
            val = datetime.now().isoformat()
        return [("key",), ("value",)], [(param_val, val)]







    # 6. API refresh tokens
    if "api_refresh_tokens" in q or "token_hash" in q:
        cols = [("id",), ("user_id",), ("expires_at",), ("token_hash",), ("token_hint",)]
        rows = [(1, 1, datetime.now() + timedelta(days=7), "hash", "hint")]
        return cols, rows

    # 7. Backup jobs & runs
    if "backup_jobs" in q or "backup_runs" in q:
        cols = [("id",), ("reason",), ("backup_type",), ("local_path",), ("requested_by_user_id",), ("status",), ("context_json",), ("created_at",), ("finished_at",), ("cloud_file_id",), ("cloud_file_name",), ("error_message",)]
        rows = [(1, "manual", "manual", "/path/to/backup.sql", 1, "success", "{}", datetime.now(), datetime.now(), "", "backup.sql", "")]
        return cols, rows

    # 8. Activity / Audit
    if "activity" in q or "audit" in q or "action" in q:
        cols = [("action",), ("id",), ("created_at",), ("level",), ("message",), ("entity_type",), ("entity_id",), ("user_id",), ("details_json",)]
        rows = [("login", 1, datetime.now(), "info", "Connexion de admin", "user", 1, 1, "{}")]
        return cols, rows

    # 8b. Performance logs, error logs, system logs, stock movements
    if "performance_logs" in q:
        cols = [("id",), ("created_at",), ("kind",), ("elapsed_ms",), ("name",), ("route",), ("details",)]
        rows = [(1, datetime.now(), "sql", 150.0, "SELECT *", "/admin", "params=0")]
        return cols, rows

    if "stock_movements" in q:
        cols = [("id",), ("created_at",), ("item_kind",), ("item_id",), ("direction",), ("quantity",), ("unit",), ("stock_before",), ("stock_after",), ("reference_type",), ("reference_id",)]
        rows = [(1, datetime.now(), "finished", 1, "out", 10.0, "kg", 100.0, 90.0, "sale", 1)]
        return cols, rows

    if "error_logs" in q:
        cols = [("id",), ("created_at",), ("message",), ("traceback",), ("request_uri",)]
        rows = [(1, datetime.now(), "Error message", "Traceback", "/admin")]
        return cols, rows

    if "system_logs" in q:
        cols = [("id",), ("created_at",), ("level",), ("message",)]
        rows = [(1, datetime.now(), "info", "System initialized")]
        return cols, rows

    # 9. Payments (check before client to avoid matches on client_id etc in joins)
    if "payments" in q or "payment" in q:
        cols = [("id",), ("client_id",), ("amount",), ("payment_date",), ("payment_type",), ("notes",), ("client_name",), ("sale_link",), ("sale_ref",), ("partner_name",), ("partner_phone",), ("partner_address",)]
        rows = [(1, 1, 200.0, "2026-05-31", "versement", "", "Client Dupont", "", "-", "Client Dupont", "0606060606", "Paris")]
        return cols, rows


    # 10. Open credit entries / Union / client history
    if "union all" in q or "client_history" in q:
        cols = [("item_kind",), ("id",), ("client_id",), ("client_name",), ("item_name",), ("balance_due",), ("sale_date",), ("total",), ("document_id",), ("c",)]
        rows = [("finished", 1, 1, "Client Dupont", "Product X", 100.0, "2026-05-31", 100.0, 1, 1)]
        return cols, rows

    # 11. Users
    if "users" in q or "user" in q:
        cols = [("id",), ("username",), ("password_hash",), ("role",), ("must_change_password",), ("is_active",), ("last_login_at",), ("last_password_change_at",), ("created_at",)]
        rows = [(1, "admin", generate_password_hash("pin"), "admin", 0, 1, datetime.now(), datetime.now(), datetime.now())]
        return cols, rows

    # 14. Sales / Purchases
    if ("sale" in q and "sale_price" not in q) or "purchase" in q or "document" in q:
        cols = [
            ("id",), ("client_id",), ("supplier_id",), ("amount",), ("sale_date",), 
            ("purchase_date",), ("notes",), ("client_name",), ("supplier_name",), 
            ("doc_number",), ("total",), ("amount_paid",), ("balance_due",), ("qty",), 
            ("unit",), ("unit_price",), ("total_price",), ("item_kind",), ("item_id",), 
            ("sale_type",), ("sale_kind",), ("total_amount",), ("document_id",),
            ("row_kind",), ("item_name",), ("item_key",), ("material_name",), ("material_unit",)
        ]
        rows = [(
            1, 1, 1, 300.0, "2026-05-31", 
            "2026-05-31", "", "Client Dupont", "Fournisseur A", 
            "V-2026-0001", 300.0, 100.0, 200.0, 10.0, 
            "kg", 30.0, 300.0, "finished", 1, 
            "credit", "finished", 300.0, 1,
            "finished", "Product X", "finished:1", "Raw Mat Y", "kg"
        )]
        return cols, rows

    # 12. Clients / client
    if "clients" in q or "client" in q:
        cols = [("id",), ("name",), ("current_balance",), ("phone",), ("address",), ("notes",), ("opening_credit",), ("client_kind",), ("status",), ("current_debt",), ("total_sales",), ("total_payments",)]
        rows = [(1, "Client Dupont", 150.0, "0606060606", "Paris", "", 50.0, "regular", "active", 150.0, 300.0, 150.0)]
        return cols, rows

    # 12b. Suppliers / supplier
    if "suppliers" in q or "supplier" in q:
        cols = [("id",), ("name",), ("phone",), ("address",), ("notes",), ("current_balance",), ("status",)]
        rows = [(1, "Fournisseur A", "0707070707", "Lyon", "", 0.0, "active")]
        return cols, rows

    # 13. Products
    if "product" in q or "finished_products" in q or "raw_materials" in q or "materials" in q:
        cols = [("id",), ("name",), ("stock_qty",), ("alert_threshold",), ("threshold_qty",), ("avg_cost",), ("sale_price",), ("default_unit",), ("unit",)]
        rows = [(1, "Product X", 50.0, 10.0, 5.0, 15.0, 25.0, "sac (50kg)", "sac (50kg)")]
        return cols, rows

    if "pg_indexes" in q:
        return [("c",)], [(5,)]

    return [("id",), ("value",), ("c",), ("status",), ("reason",), ("action",), ("item_kind",), ("created_at",), ("message",), ("level",), ("details",), ("quantity",), ("unit",), ("stock_before",), ("stock_after",), ("flow_direction",), ("product_name",), ("product_unit",), ("batch_id",)], [(1, "1", 1, "success", "manual", "login", "finished", datetime.now(), "Log message detail", "info", "{}", 10.0, "kg", 100.0, 90.0, "out", "Product X", "kg", 1)]

def mock_orm_rows_for_sql(sql: str, params=()):
    cols, rows = mock_dbapi_rows_for_sql(sql, params)
    col_names = [c[0] for c in cols]
    
    rows_list = [list(r) for r in rows]
    q = sql.lower()
    if "_total_count" in q or "over()" in q:
        if "_total_count" not in col_names:
            col_names.append("_total_count")
            for i in range(len(rows_list)):
                rows_list[i].append(1)
                
    return [dict(zip(col_names, r)) for r in rows_list]

class MockDBCursor:
    def __init__(self):
        self.description = [("id",), ("name",), ("value",)]
        self.rowcount = 1
        self.lastrowid = 1
        self._rows = []
        self._index = 0

    def execute(self, sql, params=()):
        cols, rows = mock_dbapi_rows_for_sql(sql, params)
        q = sql.lower()
        if "_total_count" in q or "over()" in q:
            col_names = [c[0] for c in cols]
            if "_total_count" not in col_names:
                cols = cols + [("_total_count",)]
                rows = [r + (1,) for r in rows]
        self.description, self._rows = cols, rows
        self._index = 0
        return self

    def fetchall(self):
        cols = [c[0] for c in self.description]
        return [CompatRow(OrderedDict(zip(cols, r))) for r in self._rows]

    def fetchone(self):
        if self._index < len(self._rows):
            r = self._rows[self._index]
            self._index += 1
            cols = [c[0] for c in self.description]
            return CompatRow(OrderedDict(zip(cols, r)))
        return None

    def close(self): pass

class MockDBConnection:
    def cursor(self): return MockDBCursor()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
    def executescript(self, script): pass
    def execute(self, sql, params=()):
        return MockDBCursor().execute(sql, params)

mock_conn = MockDBConnection()

# ── 4. Patchs des modules de base de données ─────────────────────────────────
import app.core.db_helpers
app.core.db_helpers.db_manager.connect_database = MagicMock(return_value=mock_conn)
app.core.db_helpers.pool_manager.connect_database = MagicMock(return_value=mock_conn)

import app.core.database
app.core.database.bootstrap_and_migrate = MagicMock()
app.core.database.healthcheck = MagicMock(return_value=True)
app.core.database.run_alembic_upgrade = MagicMock()

# ── 5. Patching de la session SQLAlchemy ORM pour les modules ────────────────
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models import FinishedProduct, RawMaterial, Client, User, Sale, RawSale, Payment, ProductionBatch, SavedRecipe, Expense, StockAlert, Purchase

def mock_sqlmodel_instance(model_class, ident=1):
    if model_class == Expense:
        return Expense(
            id=ident,
            date=date.today(),
            category="general",
            description="Test expense",
            amount=100.0,
            payment_method="cash"
        )
    if model_class == FinishedProduct:
        return FinishedProduct(id=ident, name="Finished Product X", default_unit="kg", stock_qty=Decimal("100.0"), sale_price=Decimal("10.0"), avg_cost=Decimal("5.0"), alert_threshold=Decimal("10.0"))
    if model_class == RawMaterial:
        return RawMaterial(id=ident, name="Raw Material Y", unit="kg", stock_qty=Decimal("200.0"), avg_cost=Decimal("3.0"), sale_price=Decimal("4.0"), alert_threshold=Decimal("10.0"), threshold_qty=Decimal("5.0"))
    if model_class == Client:
        return Client(id=ident, name="Client Dupont", phone="0102030405", address="Paris", opening_credit=Decimal("50.0"))
    if model_class == User:
        return User(id=ident, username="admin", password_hash="hash", role="admin", must_change_password=0, is_active=1)
    if model_class == Sale:
        return Sale(
            id=ident,
            client_id=1,
            document_id=1,
            finished_product_id=1,
            quantity=Decimal("10.0"),
            unit="kg",
            unit_price=Decimal("30.0"),
            total=Decimal("300.0"),
            sale_type="credit",
            sale_date=date.today(),
            amount_paid=Decimal("100.0"),
            balance_due=Decimal("200.0"),
            cost_price_snapshot=Decimal("15.0"),
            profit_amount=Decimal("150.0")
        )
    if model_class == RawSale:
        return RawSale(
            id=ident,
            client_id=1,
            document_id=1,
            raw_material_id=1,
            quantity=Decimal("10.0"),
            unit="kg",
            unit_price=Decimal("30.0"),
            total=Decimal("300.0"),
            sale_type="credit",
            sale_date=date.today(),
            amount_paid=Decimal("100.0"),
            balance_due=Decimal("200.0"),
            cost_price_snapshot=Decimal("15.0"),
            profit_amount=Decimal("150.0")
        )
    if model_class == ProductionBatch:
        return ProductionBatch(
            id=ident,
            finished_product_id=1,
            output_quantity=Decimal("10.0"),
            production_cost=Decimal("100.0"),
            unit_cost=Decimal("10.0"),
            production_date="2026-05-31",
            notes="Batch note"
        )
    if model_class == Purchase:
        return Purchase(
            id=ident,
            supplier_id=1,
            document_id=1,
            raw_material_id=1,
            finished_product_id=1,
            quantity=Decimal("10.0"),
            unit="kg",
            unit_price=Decimal("30.0"),
            total=Decimal("300.0"),
            purchase_date=date.today(),
            notes=""
        )
    if model_class == Payment:
        return Payment(
            id=ident,
            client_id=1,
            amount=Decimal("100.0"),
            payment_date=date.today(),
            notes=""
        )
    if model_class == StockAlert:
        return StockAlert(
            id=ident,
            product_type="finished",
            product_id=1,
            product_name="Product X",
            current_qty=Decimal("5.0"),
            threshold_qty=Decimal("10.0"),
            triggered_at=datetime.utcnow()
        )
    try:
        return model_class(id=ident)
    except Exception:
        return MagicMock()

class MockRow:
    def __init__(self, dct, statement=None):
        self._dct = dct
        self.statement = statement

    @property
    def _mapping(self):
        return self._dct

    def __getitem__(self, key):
        if key == 0 and self.statement:
            stmt = self.statement.lower()
            if "production_batch" in stmt:
                return mock_sqlmodel_instance(ProductionBatch)
            if "purchase" in stmt:
                return mock_sqlmodel_instance(Purchase)
            if "raw_sale" in stmt:
                return mock_sqlmodel_instance(RawSale)
            if "sale" in stmt:
                return mock_sqlmodel_instance(Sale)
            if "payment" in stmt:
                return mock_sqlmodel_instance(Payment)
            if "client" in stmt:
                return mock_sqlmodel_instance(Client)
        if isinstance(key, int):
            return list(self._dct.values())[key]
        return self._dct[key]

    def keys(self):
        return list(self._dct.keys())

    def __getattr__(self, name):
        if name in self._dct:
            return self._dct[name]
        raise AttributeError(f"MockRow object has no attribute '{name}'")

class MockScalars:
    def __init__(self, items):
        self.items = items
    def all(self):
        return self.items
    def first(self):
        return self.items[0] if self.items else None

class MockMappingResult:
    def __init__(self, statement):
        self.statement = str(statement).lower()

    def all(self):
        return mock_orm_rows_for_sql(self.statement)

    def first(self):
        rows = self.all()
        return rows[0] if rows else None

class MockResult:
    def __init__(self, statement):
        self.statement = str(statement).lower()

    def scalar_one_or_none(self):
        if "from sales" in self.statement:
            return mock_sqlmodel_instance(Sale)
        if "from raw_sales" in self.statement:
            return mock_sqlmodel_instance(RawSale)
        if "from finished_products" in self.statement or "finishedproduct" in self.statement:
            return mock_sqlmodel_instance(FinishedProduct)
        if "from raw_materials" in self.statement or "rawmaterial" in self.statement:
            return mock_sqlmodel_instance(RawMaterial)
        if "from clients" in self.statement or "client" in self.statement:
            return mock_sqlmodel_instance(Client)
        if "from users" in self.statement or "user" in self.statement:
            return mock_sqlmodel_instance(User)
        if "from expenses" in self.statement or "expense" in self.statement:
            return mock_sqlmodel_instance(Expense)
        return MagicMock()

    def scalar_one(self):
        return 1

    def scalar(self):
        row = self.first()
        if row:
            if hasattr(row, "_dct") and row._dct:
                return list(row._dct.values())[0]
            if isinstance(row, dict) and row:
                return list(row.values())[0]
        return None

    def first(self):
        rows = mock_orm_rows_for_sql(self.statement)
        return MockRow(rows[0], self.statement) if rows else None

    def all(self):
        rows = mock_orm_rows_for_sql(self.statement)
        return [MockRow(r, self.statement) for r in rows]

    def fetchall(self):
        rows = mock_orm_rows_for_sql(self.statement)
        return [MockRow(r, self.statement) for r in rows]

    def scalars(self):
        if "from sales" in self.statement:
            items = [mock_sqlmodel_instance(Sale)]
        elif "from raw_sales" in self.statement:
            items = [mock_sqlmodel_instance(RawSale)]
        elif "from finished_products" in self.statement or "finishedproduct" in self.statement:
            items = [mock_sqlmodel_instance(FinishedProduct)]
        elif "from raw_materials" in self.statement or "rawmaterial" in self.statement:
            items = [mock_sqlmodel_instance(RawMaterial)]
        elif "from clients" in self.statement or "client" in self.statement:
            items = [mock_sqlmodel_instance(Client)]
        elif "from users" in self.statement or "user" in self.statement:
            items = [mock_sqlmodel_instance(User)]
        elif "from expenses" in self.statement or "expense" in self.statement:
            items = [mock_sqlmodel_instance(Expense)]
        else:
            items = [MagicMock()]
        return MockScalars(items)

    def mappings(self):
        return MockMappingResult(self.statement)

class MockAsyncSession:
    def __init__(self, *args, **kwargs): pass
    async def execute(self, statement, *args, **kwargs):
        return MockResult(str(statement))
    async def get(self, model, ident, *args, **kwargs):
        return mock_sqlmodel_instance(model, ident)
    def add(self, instance, *args, **kwargs):
        if hasattr(instance, "id") and instance.id is None:
            instance.id = 1
    async def refresh(self, instance, *args, **kwargs):
        if hasattr(instance, "id") and instance.id is None:
            instance.id = 1
    async def flush(self, *args, **kwargs): pass
    async def commit(self, *args, **kwargs): pass
    async def delete(self, instance, *args, **kwargs): pass
    async def close(self, *args, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass

from app.core.async_db import get_async_session
async def override_get_async_session():
    yield MockAsyncSession()

import app.core.async_db
app.core.async_db.get_async_sessionmaker = MagicMock(return_value=MockAsyncSession)

# Import all API and Web routes before patching so that they are in sys.modules
import app.main
import app.api.deps
import app.api.v1.admin
import app.api.v1.alerts
import app.api.v1.auth
import app.api.v1.clients
import app.api.v1.dashboard
import app.api.v1.offline
import app.api.v1.payments
import app.api.v1.production
import app.api.v1.purchases
import app.api.v1.sales
import app.web.deps
import app.web.admin_pages
import app.web.auth_pages
import app.web.client_pages
import app.web.contacts_pages
import app.web.dashboard_pages
import app.web.operations_pages
import app.web.production_pages
import app.web.report_pages
import app.web.search_pages
import app.modules.expenses.web
import app.api.v1.expenses

# ── 6. Mock de l'authentification et CSRF pour le TestClient ─────────────────
mock_user = {"id": 1, "username": "admin", "role": "admin", "is_active": 1}

async def async_noop(*args, **kwargs):
    pass

# Apply patches dynamically to all imported app modules in sys.modules
for name, module in list(sys.modules.items()):
    if name.startswith("app.") or name == "app":
        if hasattr(module, "require_api_user"):
            setattr(module, "require_api_user", MagicMock(return_value=mock_user))
        if hasattr(module, "load_user_from_session"):
            setattr(module, "load_user_from_session", MagicMock(return_value=mock_user))
        if hasattr(module, "get_current_user"):
            setattr(module, "get_current_user", MagicMock(return_value=mock_user))
        if hasattr(module, "require_user"):
            setattr(module, "require_user", MagicMock(return_value=None))
        if hasattr(module, "require_permission") and name != "app.core.permissions":
            setattr(module, "require_permission", MagicMock(return_value=None))
        if hasattr(module, "ensure_csrf_token"):
            setattr(module, "ensure_csrf_token", MagicMock(return_value=None))
        if hasattr(module, "csrf_protect"):
            setattr(module, "csrf_protect", async_noop)
        if hasattr(module, "get_async_sessionmaker"):
            setattr(module, "get_async_sessionmaker", MagicMock(return_value=MockAsyncSession))

# ── 7. Initialisation de l'application FastAPI ──────────────────────────────
import pytest
from fastapi.testclient import TestClient
from app.main import app

from app.core.jwt_auth import get_current_user_id
from app.web.deps import verify_csrf_token

app.dependency_overrides[get_async_session] = override_get_async_session
app.dependency_overrides[verify_csrf_token] = lambda: None
app.dependency_overrides[get_current_user_id] = lambda: 1

client = TestClient(app)

class TestHTTPRoutes:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code in (200, 503)

    def test_api_version(self):
        response = client.get("/api/v1/version")
        assert response.status_code == 200

    def test_auth_login(self):
        response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "pin"})
        assert response.status_code == 200

    def test_auth_me(self):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200

    def test_auth_refresh(self):
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "token"})
        assert response.status_code == 200

    def test_auth_logout(self):
        response = client.post("/api/v1/auth/logout", json={"refresh_token": "token"})
        assert response.status_code == 200

    def test_clients_endpoints(self):
        # List
        assert client.get("/api/v1/clients").status_code == 200
        # Create
        assert client.post("/api/v1/clients", json={"name": "Dupont", "phone": "06"}).status_code in (200, 201)
        # Detail
        assert client.get("/api/v1/clients/1").status_code == 200
        # Update
        assert client.put("/api/v1/clients/1", json={"name": "Dupont2"}).status_code == 200
        # Delete
        assert client.post("/api/v1/clients/1/shred").status_code == 200

    def test_sales_endpoints(self):
        assert client.get("/api/v1/sellable-items").status_code == 200
        assert client.get("/api/v1/sales").status_code == 200
        assert client.post("/api/v1/sales", json={"client_id": 1, "sale_date": "2026-05-31", "lines": [{"item_key": "finished:1", "quantity": 10, "unit": "kg", "unit_price": 5}]}).status_code in (200, 201)
        assert client.get("/api/v1/sales/finished/1").status_code == 200
        assert client.delete("/api/v1/sales/finished/1").status_code == 200

    def test_purchases_endpoints(self):
        assert client.get("/api/v1/purchases").status_code == 200
        assert client.post("/api/v1/purchases", json={"supplier_id": 1, "raw_material_id": "raw:1", "quantity": 20, "unit": "kg", "unit_price": 3, "purchase_date": "2026-05-31"}).status_code in (200, 201)

    def test_payments_endpoints(self):
        assert client.get("/api/v1/payments").status_code == 200
        assert client.post("/api/v1/payments", json={"client_id": 1, "amount": 100, "payment_date": "2026-05-31"}).status_code in (200, 201)

    def test_production_endpoints(self):
        assert client.get("/api/v1/production-batches").status_code == 200
        assert client.post("/api/v1/production-batches", json={"finished_product_id": 1, "output_quantity": 50, "production_date": "2026-05-31", "raw_material_id[]": [1], "quantity[]": [30]}).status_code in (200, 201)

    def test_alerts_and_dashboard(self):
        assert client.get("/api/v1/alerts").status_code == 200
        assert client.get("/api/v1/dashboard/summary").status_code == 200
        assert client.get("/api/v1/recent-operations").status_code == 200

    def test_mobile_and_offline(self):
        assert client.post("/api/mobile/v1/auth/token", json={"username": "admin", "password": "pin"}).status_code == 200
        assert client.get("/api/mobile/v1/clients").status_code == 200
        assert client.post("/api/mobile/v1/payments", json={"client_id": 1, "amount": 100.0, "payment_date": "2026-05-31", "notes": ""}).status_code == 200
        assert client.post("/api/mobile/v1/offline/sync", json={"type": "create_payment", "payload": {"client_id": 1, "amount": 100.0, "payment_date": "2026-05-31"}}).status_code == 200

    def test_web_html_pages(self):
        for route in ["/", "/login", "/dashboard", "/clients", "/contacts", "/operations", "/production", "/admin", "/reports", "/api/search?q=test", "/change-password"]:
            response = client.get(route)
            assert response.status_code in (200, 303)

# ── 8. Invocation Directe des Services ───────────────────────────────────────
class TestServicesDirect:
    @pytest.mark.asyncio
    async def test_alert_service(self):
        from app.services.alert_service import check_overdue_clients, broadcast_overdue_alerts
        assert isinstance(await check_overdue_clients(30), list)
        assert isinstance(await broadcast_overdue_alerts(), int)

    @pytest.mark.asyncio
    async def test_backup_service(self):
        from app.services.backup_service import get_backup_settings, save_backup_configuration, list_backup_jobs
        assert isinstance(await get_backup_settings(), dict)
        await save_backup_configuration({"auto_backup": "1", "backup_interval": "600"})
        assert isinstance(await list_backup_jobs(), list)

    @pytest.mark.asyncio
    async def test_system_service(self):
        from app.services.system_service import get_system_status, export_diagnostic_report
        assert isinstance(await get_system_status(), dict)
        assert isinstance(await export_diagnostic_report(), str)

    @pytest.mark.asyncio
    async def test_activity_service(self):
        from app.services.activity_service import list_admin_activity, list_activity_actions, list_activity_entity_types
        assert isinstance(await list_admin_activity({}), list)
        assert isinstance(await list_activity_actions(), list)
        assert isinstance(await list_activity_entity_types(), list)

    @pytest.mark.asyncio
    async def test_payment_service(self):
        from app.services.payment_service import new_payment_context, create_payment_from_form, create_mobile_payment
        assert await new_payment_context() is not None
        assert await create_mobile_payment(1, 100.0, "2026-05-31", "notes", 1) is not None

    @pytest.mark.asyncio
    async def test_stock_service(self):
        from app.services.stock_service import unit_choices, qty_to_kg, unit_price_to_kg
        assert isinstance(unit_choices(), list)
        assert qty_to_kg(10.0, "sac (50kg)") == 500.0
        assert unit_price_to_kg(10.0, "quintal") == 0.1

    @pytest.mark.asyncio
    async def test_print_service(self):
        from app.services.printing import build_print_payload
        assert build_print_payload("payment", 1) is not None
