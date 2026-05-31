"""
Tests unitaires — couverture 100 % sur tous les modules purs.
Aucune base de données ni connexion réseau nécessaire.
Tout ce qui touche DB/Redis est mocké via unittest.mock.
"""
from __future__ import annotations

import os
import sys
import pickle
import time
import threading
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from time import monotonic
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import pytest

# ── Variables d'environnement AVANT tout import app ──────────────────────────
os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest-unit-only")
os.environ.setdefault("FASTAPI_ENV", "test")
os.environ.setdefault("FAB_DESKTOP", "0")
os.environ.setdefault("DATABASE_URL", "postgresql://fake@localhost/fake_test")
os.environ.setdefault("REDIS_URL", "")            # Pas de Redis en tests unitaires
os.environ.setdefault("FAB_DISABLE_BACKGROUND_JOBS", "1")


# =============================================================================
# 1. app.version
# =============================================================================

class TestVersion:
    def test_version_string_not_empty(self):
        from app.version import APP_VERSION
        assert isinstance(APP_VERSION, str) and len(APP_VERSION) > 0

    def test_version_label_starts_with_v(self):
        from app.version import VERSION_LABEL
        assert VERSION_LABEL.startswith("v")


# =============================================================================
# 2. app.core.exceptions
# =============================================================================

class TestExceptions:
    def test_business_error_basic(self):
        from app.core.exceptions import BusinessError
        err = BusinessError("test message", code="test_code")
        assert str(err) == "test message"
        assert err.code == "test_code"
        assert err.details == {}

    def test_business_error_with_details(self):
        from app.core.exceptions import BusinessError
        err = BusinessError("msg", details={"key": "val"})
        assert err.details == {"key": "val"}

    def test_not_found_error(self):
        from app.core.exceptions import NotFoundError
        err = NotFoundError("Client", 42)
        assert err.code == "not_found"
        assert "42" in err.message

    def test_validation_error_without_field(self):
        from app.core.exceptions import ValidationError
        err = ValidationError("champ requis")
        assert err.code == "validation_error"
        assert err.field is None

    def test_validation_error_with_field(self):
        from app.core.exceptions import ValidationError
        err = ValidationError("champ requis", field="nom")
        assert err.field == "nom"
        assert err.details == {"field": "nom"}

    def test_conflict_error(self):
        from app.core.exceptions import ConflictError
        assert ConflictError("doublon").code == "conflict"

    def test_permission_denied_error(self):
        from app.core.exceptions import PermissionDeniedError
        assert PermissionDeniedError().code == "permission_denied"

    def test_authentication_required_error(self):
        from app.core.exceptions import AuthenticationRequiredError
        assert AuthenticationRequiredError().code == "authentication_required"

    def test_friendly_business_error(self):
        from app.core.exceptions import get_friendly_error_message, BusinessError
        assert get_friendly_error_message(BusinessError("erreur métier")) == "erreur métier"

    def test_friendly_value_error(self):
        from app.core.exceptions import get_friendly_error_message
        assert get_friendly_error_message(ValueError("valeur invalide")) == "valeur invalide"

    def test_friendly_foreign_key(self):
        from app.core.exceptions import get_friendly_error_message
        msg = get_friendly_error_message(Exception("violates foreign key constraint"))
        assert "lié" in msg or "impossible" in msg

    def test_friendly_unique_constraint(self):
        from app.core.exceptions import get_friendly_error_message
        msg = get_friendly_error_message(Exception("unique constraint violation"))
        assert "existe déjà" in msg or "unique" in msg.lower()

    def test_friendly_numeric_range(self):
        from app.core.exceptions import get_friendly_error_message
        msg = get_friendly_error_message(Exception("numeric value out of range"))
        assert "montant" in msg or "quantité" in msg or "limite" in msg

    def test_friendly_generic(self):
        from app.core.exceptions import get_friendly_error_message
        msg = get_friendly_error_message(RuntimeError("quelque chose"))
        assert isinstance(msg, str)

    def test_friendly_pydantic_error(self):
        from app.core.exceptions import get_friendly_error_message
        from pydantic import BaseModel, ValidationError as PydanticValidationError
        class M(BaseModel):
            x: int
        try:
            M(x="not_an_int")
        except PydanticValidationError as exc:
            msg = get_friendly_error_message(exc)
            assert isinstance(msg, str) and len(msg) > 0


# =============================================================================
# 3. app.core.permissions
# =============================================================================

class TestPermissions:
    def test_normalize_roles(self):
        from app.core.permissions import normalize_role
        assert normalize_role("admin") == "admin"
        assert normalize_role("manager") == "manager"
        assert normalize_role("operator") == "operator"
        assert normalize_role("user") == "operator"
        assert normalize_role("unknown") == "operator"
        assert normalize_role(None) == "operator"

    def test_admin_has_all_permissions(self):
        from app.core.permissions import has_permission, ALL_PERMISSIONS
        user = {"role": "admin"}
        for perm in ALL_PERMISSIONS:
            assert has_permission(user, perm) is True

    def test_no_user_returns_false(self):
        from app.core.permissions import has_permission
        assert has_permission(None, "dashboard.read") is False

    def test_none_permission_returns_true(self):
        from app.core.permissions import has_permission
        assert has_permission(None, None) is True

    def test_operator_allowed(self):
        from app.core.permissions import has_permission
        assert has_permission({"role": "operator"}, "dashboard.read") is True

    def test_operator_forbidden(self):
        from app.core.permissions import has_permission
        assert has_permission({"role": "operator"}, "backup.restore") is False

    def test_permission_for_endpoint_public(self):
        from app.core.permissions import permission_for_endpoint
        assert permission_for_endpoint("login") is None
        assert permission_for_endpoint("health") is None
        assert permission_for_endpoint(None) is None

    def test_permission_for_endpoint_dashboard(self):
        from app.core.permissions import permission_for_endpoint
        assert permission_for_endpoint("dashboard") == "dashboard.read"

    def test_permission_for_endpoint_method(self):
        from app.core.permissions import permission_for_endpoint
        assert permission_for_endpoint("clients", "GET") == "contacts.read"
        assert permission_for_endpoint("clients", "POST") == "contacts.write"
        assert permission_for_endpoint("clients", "OPTIONS") is None

    def test_all_permissions_constants(self):
        from app.core.permissions import (
            PERMISSION_DASHBOARD_READ, ALL_PERMISSIONS,
            ROLE_PERMISSIONS, ROLE_ADMIN
        )
        assert PERMISSION_DASHBOARD_READ in ALL_PERMISSIONS
        assert ALL_PERMISSIONS == ROLE_PERMISSIONS[ROLE_ADMIN]

    def test_manager_permissions_subset(self):
        from app.core.permissions import MANAGER_PERMISSIONS, ALL_PERMISSIONS
        assert MANAGER_PERMISSIONS.issubset(ALL_PERMISSIONS)

    def test_operator_permissions_subset(self):
        from app.core.permissions import ROLE_PERMISSIONS, ALL_PERMISSIONS, ROLE_OPERATOR
        assert ROLE_PERMISSIONS[ROLE_OPERATOR].issubset(ALL_PERMISSIONS)

    def test_has_permission_object_with_role_attr(self):
        from app.core.permissions import has_permission
        class FakeUser:
            role = "admin"
        assert has_permission(FakeUser(), "dashboard.read") is True

    def test_require_permission_no_user(self):
        from app.core.permissions import require_permission
        with patch("app.core.permissions.get_state_value", return_value=None), \
             patch("app.core.permissions.permission_denied_response", return_value="denied"):
            result = require_permission("dashboard.read")(lambda: "ok")()
            assert result == "denied"

    # Manager branches (lignes non couvertes)
    def test_manager_blocked_on_purchases_path(self):
        from app.core.permissions import has_permission, PERMISSION_OPERATIONS_WRITE
        req = MagicMock()
        req.url.path = "/purchases/new"
        req.query_params = {}
        with patch("app.core.permissions.get_state_value", return_value=req):
            assert has_permission({"role": "manager"}, PERMISSION_OPERATIONS_WRITE) is False

    def test_manager_blocked_by_query_param(self):
        from app.core.permissions import has_permission, PERMISSION_OPERATIONS_WRITE
        req = MagicMock()
        req.url.path = "/operations/new"
        req.query_params = {"type": "purchase"}
        with patch("app.core.permissions.get_state_value", return_value=req):
            assert has_permission({"role": "manager"}, PERMISSION_OPERATIONS_WRITE) is False

    def test_manager_allowed_non_purchase(self):
        from app.core.permissions import has_permission, PERMISSION_OPERATIONS_WRITE
        req = MagicMock()
        req.url.path = "/sales/new"
        req.query_params = {}
        with patch("app.core.permissions.get_state_value", return_value=req):
            assert has_permission({"role": "manager"}, PERMISSION_OPERATIONS_WRITE) is True

    def test_manager_no_request_in_state(self):
        from app.core.permissions import has_permission, PERMISSION_OPERATIONS_WRITE
        with patch("app.core.permissions.get_state_value", return_value=None):
            assert has_permission({"role": "manager"}, PERMISSION_OPERATIONS_WRITE) is True

    def test_manager_backup_forbidden(self):
        from app.core.permissions import has_permission, PERMISSION_BACKUP_RESTORE
        assert has_permission({"role": "manager"}, PERMISSION_BACKUP_RESTORE) is False

    def test_dynamic_permissions_granted(self):
        from app.core import permissions as p
        p._dynamic_permissions_cache = {"operator": {"dyn.perm"}}
        assert p.has_permission({"role": "operator"}, "dyn.perm") is True
        p._dynamic_permissions_cache = None

    def test_dynamic_permissions_not_granted(self):
        from app.core import permissions as p
        p._dynamic_permissions_cache = {"operator": set()}
        assert p.has_permission({"role": "operator"}, "missing") is False
        p._dynamic_permissions_cache = None

    def test_require_permission_no_perm(self):
        from app.core.permissions import require_permission
        with patch("app.core.permissions.get_state_value", return_value={"role": "operator"}), \
             patch("app.core.permissions.has_permission", return_value=False), \
             patch("app.core.permissions.permission_denied_response", return_value="denied"):
            assert require_permission("backup.restore")(lambda: "ok")() == "denied"

    def test_require_permission_grants(self):
        from app.core.permissions import require_permission
        with patch("app.core.permissions.get_state_value", return_value={"role": "admin"}), \
             patch("app.core.permissions.has_permission", return_value=True):
            assert require_permission("dashboard.read")(lambda: "ok")() == "ok"

    def test_get_dynamic_permissions_cache_hit(self):
        from app.core import permissions as p
        p._dynamic_permissions_cache = {"manager": {"cached.perm"}}
        assert "cached.perm" in p._get_dynamic_permissions("manager")
        p._dynamic_permissions_cache = None

    def test_get_dynamic_permissions_unknown_role(self):
        from app.core import permissions as p
        p._dynamic_permissions_cache = {}
        assert p._get_dynamic_permissions("ghost") == set()
        p._dynamic_permissions_cache = None


# =============================================================================
# 4. app.core.security
# =============================================================================

class TestPasswordValidation:
    def test_pin_valid(self):
        from app.core.security import validate_password_strength
        ok, msg = validate_password_strength("1234", mode="pin")
        assert ok is True and msg == ""

    def test_pin_too_short(self):
        from app.core.security import validate_password_strength
        ok, _ = validate_password_strength("123", mode="pin")
        assert ok is False

    def test_pin_too_long(self):
        from app.core.security import validate_password_strength
        ok, _ = validate_password_strength("12345", mode="pin")
        assert ok is False

    def test_pin_non_digits(self):
        from app.core.security import validate_password_strength
        ok, _ = validate_password_strength("ab12", mode="pin")
        assert ok is False

    def test_password_valid(self):
        from app.core.security import validate_password_strength
        ok, _ = validate_password_strength("Password1", mode="password")
        assert ok is True

    def test_password_too_short(self):
        from app.core.security import validate_password_strength
        ok, _ = validate_password_strength("Pass1", mode="password")
        assert ok is False

    def test_password_no_digit(self):
        from app.core.security import validate_password_strength
        ok, msg = validate_password_strength("Password", mode="password")
        assert ok is False and "chiffre" in msg

    def test_password_no_letter(self):
        from app.core.security import validate_password_strength
        ok, msg = validate_password_strength("12345678", mode="password")
        assert ok is False and "lettre" in msg


class TestEncryptDecrypt:
    def _key(self): return os.urandom(32)

    def test_encrypt_none_returns_none(self):
        from app.core.security import encrypt_val
        assert encrypt_val(None, self._key()) is None

    def test_decrypt_none_returns_none(self):
        from app.core.security import decrypt_val
        assert decrypt_val(None, self._key()) is None

    def test_decrypt_empty_string(self):
        from app.core.security import decrypt_val
        assert decrypt_val("", self._key()) == ""

    def test_round_trip(self):
        from app.core.security import encrypt_val, decrypt_val
        key = self._key()
        encrypted = encrypt_val("données secrètes 123", key)
        assert encrypted.startswith("ale:")
        assert decrypt_val(encrypted, key) == "données secrètes 123"

    def test_wrong_key(self):
        from app.core.security import encrypt_val, decrypt_val
        enc = encrypt_val("secret", self._key())
        assert decrypt_val(enc, self._key()) == "[DONNÉES SUPPRIMÉES]"

    def test_no_key(self):
        from app.core.security import decrypt_val
        assert decrypt_val("ale:somebase64data", None) == "[DONNÉES SUPPRIMÉES]"

    def test_plain_passthrough(self):
        from app.core.security import decrypt_val
        assert decrypt_val("non_encrypted", self._key()) == "non_encrypted"

    def test_truncated_ale(self):
        from app.core.security import decrypt_val
        import base64
        short = base64.b64encode(b"abc").decode()
        assert decrypt_val(f"ale:{short}", self._key()) == "[DONNÉES SUPPRIMÉES]"


class TestClientIp:
    def test_no_request(self):
        from app.core.security import client_ip
        with patch("app.core.security.get_state_value", return_value=None):
            assert client_ip() == "unknown"

    def test_direct_ip(self):
        from app.core.security import client_ip
        req = MagicMock()
        req.client.host = "192.168.1.1"
        req.headers.get.return_value = ""
        with patch("app.core.security.get_state_value", return_value=req), \
             patch("app.core.security._TRUSTED_PROXIES", frozenset()):
            assert client_ip() == "192.168.1.1"

    def test_trusted_proxy(self):
        from app.core.security import client_ip
        req = MagicMock()
        req.client.host = "10.0.0.1"
        req.headers.get.return_value = "203.0.113.5, 10.0.0.1"
        with patch("app.core.security.get_state_value", return_value=req), \
             patch("app.core.security._TRUSTED_PROXIES", frozenset(["10.0.0.1"])):
            assert client_ip() == "203.0.113.5"


class TestSecurityRateLimit:
    def setup_method(self):
        from app.core.rate_limit_store import RateLimitStore
        RateLimitStore.clear_all()

    def test_consume_rate_limit(self):
        from app.core.security import consume_rate_limit
        assert consume_rate_limit("key1", 10, 60) is True

    def test_is_locked_out_false(self):
        from app.core.security import is_locked_out
        assert is_locked_out("clean_ip") is False

    def test_record_and_clear_login_failure(self):
        from app.core.security import record_login_failure, clear_login_failures, is_locked_out
        for _ in range(3):
            record_login_failure("ip_test")
        clear_login_failures("ip_test")
        assert is_locked_out("ip_test") is False

    def test_get_client_fingerprint(self):
        from app.core.security import get_client_fingerprint
        req = MagicMock()
        req.headers.get.return_value = "Mozilla/5.0"
        with patch("app.core.security.client_ip", return_value="10.0.0.1"):
            fp = get_client_fingerprint(req)
            assert isinstance(fp, str) and len(fp) == 64


# =============================================================================
# 5. app.core.jwt_auth
# =============================================================================

class TestJwtAuth:
    def test_create_and_decode_access_token(self):
        from app.core.jwt_auth import create_access_token, decode_token
        token = create_access_token(user_id=1, role="admin")
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        from app.core.jwt_auth import create_refresh_token, decode_token
        token = create_refresh_token(user_id=5)
        payload = decode_token(token)
        assert payload["sub"] == "5"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_raises(self):
        from app.core.jwt_auth import decode_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_token("not.a.valid.jwt")
        assert exc.value.status_code == 401

    def test_decode_tampered_token_raises(self):
        from app.core.jwt_auth import create_access_token, decode_token
        from fastapi import HTTPException
        token = create_access_token(1, "admin")
        with pytest.raises(HTTPException):
            decode_token(token[:-4] + "xxxx")

    def test_token_expire_constants(self):
        from app.core.jwt_auth import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
        assert ACCESS_TOKEN_EXPIRE_MINUTES > 0
        assert REFRESH_TOKEN_EXPIRE_DAYS > 0

    def test_get_current_user_id_no_credentials(self):
        from app.core.jwt_auth import get_current_user_id
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(credentials=None)
        assert exc.value.status_code == 401

    def test_get_current_user_id_wrong_type(self):
        from app.core.jwt_auth import get_current_user_id, create_refresh_token
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_refresh_token(99))
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(credentials=creds)
        assert exc.value.status_code == 401

    def test_get_current_user_id_valid(self):
        from app.core.jwt_auth import get_current_user_id, create_access_token
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_access_token(user_id=7, role="operator"))
        assert get_current_user_id(credentials=creds) == 7


# =============================================================================
# 6. app.core.config
# =============================================================================

class TestConfig:
    def test_env_is_test(self):
        from app.core.config import settings
        assert settings.env == "test"

    def test_secret_key_set(self):
        from app.core.config import settings
        assert len(settings.secret_key) > 0

    def test_database_url_postgres(self):
        from app.core.config import settings
        url = settings.database_url
        assert url.startswith("postgresql://") or url.startswith("postgres://")

    def test_worker_count_default(self):
        from app.core.config import configured_worker_count
        for var in ("FAB_WORKERS", "WEB_CONCURRENCY", "UVICORN_WORKERS", "GUNICORN_WORKERS"):
            os.environ.pop(var, None)
        assert configured_worker_count() >= 1

    def test_worker_count_env(self):
        from app.core.config import configured_worker_count
        os.environ["FAB_WORKERS"] = "4"
        count = configured_worker_count()
        os.environ.pop("FAB_WORKERS")
        assert count == 4

    def test_worker_count_invalid_fallback(self):
        from app.core.config import configured_worker_count
        os.environ["FAB_WORKERS"] = "bad"
        for v in ("WEB_CONCURRENCY", "UVICORN_WORKERS", "GUNICORN_WORKERS"):
            os.environ.pop(v, None)
        count = configured_worker_count()
        os.environ.pop("FAB_WORKERS")
        assert count >= 1

    def test_database_url_not_postgres_raises(self):
        from app.core.config import Settings
        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        try:
            s = Settings()
            with pytest.raises(RuntimeError, match="PostgreSQL"):
                _ = s.database_url
        finally:
            if old: os.environ["DATABASE_URL"] = old
            else: os.environ.pop("DATABASE_URL", None)

    def test_database_url_empty_raises(self):
        from app.core.config import Settings
        old = os.environ.pop("DATABASE_URL", None)
        try:
            s = Settings()
            with pytest.raises(RuntimeError, match="DATABASE_URL"):
                _ = s.database_url
        finally:
            if old: os.environ["DATABASE_URL"] = old

    def test_debug_property(self):
        from app.core.config import Settings
        s = Settings.__new__(Settings)
        object.__setattr__(s, "env", "development")
        assert s.debug is True
        object.__setattr__(s, "env", "production")
        assert s.debug is False


# =============================================================================
# 7. app.core.perf_cache — InMemoryCache
# =============================================================================

class TestInMemoryCache:
    def _cache(self):
        from app.core.perf_cache import InMemoryCache
        return InMemoryCache()

    def test_get_missing_returns_none(self):
        assert self._cache().get(("missing",)) is None

    def test_set_and_get(self):
        c = self._cache()
        key = ("k",)
        c.set(key, "hello", ttl=60.0, fingerprint=f"v:{c.cache_generation()}")
        assert c.get(key) == "hello"

    def test_expiry(self):
        c = self._cache()
        key = ("exp",)
        c.set(key, "val", ttl=10.0, fingerprint=f"v:{c.cache_generation()}")
        with c._lock:
            c._cache[key]["expires_at"] = monotonic() - 1.0
        assert c.get(key) is None

    def test_bump_generation(self):
        c = self._cache()
        g0 = c.cache_generation()
        assert c.bump_cache_generation() == g0 + 1

    def test_clear(self):
        c = self._cache()
        key = ("k",)
        c.set(key, "v", ttl=60, fingerprint=f"v:{c.cache_generation()}")
        c.clear()
        assert c.get(key) is None

    def test_entry_count(self):
        c = self._cache()
        assert c.entry_count() == 0
        c.set(("x",), 1, ttl=60, fingerprint=f"v:{c.cache_generation()}")
        assert c.entry_count() == 1

    def test_invalidate_domains(self):
        c = self._cache()
        key = ("sales", "list")
        c.set(key, [1, 2], ttl=60, fingerprint=f"v:{c.cache_generation()}")
        c.invalidate_domains("sales")
        assert c.get(key) is None

    def test_thread_safety(self):
        c = self._cache()
        errors = []
        def worker(i):
            try:
                k = (f"k{i}",)
                c.set(k, i, ttl=10, fingerprint=f"v:{c.cache_generation()}")
                c.get(k)
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert errors == []


class TestSafeInt:
    def test_none(self):
        from app.core.perf_cache import _safe_int
        assert _safe_int(None) == 0

    def test_valid(self):
        from app.core.perf_cache import _safe_int
        assert _safe_int(42) == 42
        assert _safe_int("7") == 7

    def test_invalid(self):
        from app.core.perf_cache import _safe_int
        assert _safe_int("abc") == 0

    def test_mock(self):
        from app.core.perf_cache import _safe_int
        assert _safe_int(MagicMock()) == 0


class TestCacheTTLConstants:
    def test_ordering(self):
        from app.core.perf_cache import TTL_STABLE, TTL_SEMI_STABLE, TTL_FREQUENT, TTL_REALTIME
        assert TTL_STABLE > TTL_SEMI_STABLE > TTL_FREQUENT > TTL_REALTIME > 0

    def test_values(self):
        from app.core.perf_cache import TTL_STABLE, TTL_SEMI_STABLE, TTL_FREQUENT, TTL_REALTIME
        assert TTL_STABLE == 3600.0
        assert TTL_SEMI_STABLE == 300.0
        assert TTL_FREQUENT == 30.0
        assert TTL_REALTIME == 2.0


# =============================================================================
# 8. app.core.perf_cache — HybridCache (Redis mocké, thread supprimé)
# =============================================================================

class TestHybridCache:
    """Thread Redis pubsub supprimé dans tous les tests via _start_invalidation_listener mock."""

    def _make(self):
        from app.core.perf_cache import HybridCache
        mc = MagicMock()
        mc.keys.return_value = []
        with patch("redis.from_url", return_value=mc), \
             patch.object(HybridCache, "_start_invalidation_listener"):
            return HybridCache("redis://localhost:6379"), mc

    def test_l1_hit(self):
        from app.core.perf_cache import InMemoryCache
        cache, _ = self._make()
        assert isinstance(cache.l1, InMemoryCache)
        key = ("hk",)
        cache.set(key, "val", ttl=10, fingerprint=f"v:{cache.cache_generation()}")
        assert cache.l1.get(key) == "val"

    def test_l2_fallback(self):
        cache, mc = self._make()
        key = ("l2k",)
        ver = cache.cache_generation()
        cache.set(key, "from_l2", ttl=60, fingerprint=f"v:{ver}")
        cache.l1.clear()
        mc.get.return_value = pickle.dumps({"value": "from_l2", "fingerprint": f"v:{ver}"})
        with patch.object(cache.l2, "cache_generation", return_value=ver):
            assert cache.get(key) == "from_l2"

    def test_clear(self):
        cache, mc = self._make()
        cache.clear()
        mc.keys.assert_called()

    def test_bump_generation(self):
        cache, mc = self._make()
        mc.incr.return_value = 3
        assert cache.bump_cache_generation() == 3

    def test_invalidate_domains(self):
        cache, mc = self._make()
        cache.invalidate_domains("sales", "clients")
        mc.hincrby.assert_called()

    def test_entry_count(self):
        cache, _ = self._make()
        assert isinstance(cache.entry_count(), int)


# =============================================================================
# 9. app.core.rate_limit_store
# =============================================================================

class TestRateLimitStore:
    def _store(self):
        from app.core.rate_limit_store import _InMemoryRateLimitStore
        return _InMemoryRateLimitStore()

    def test_consume_within_limit(self):
        assert self._store().consume("ip1", limit=5, window_seconds=60) is True

    def test_consume_exceeds_limit(self):
        s = self._store()
        for _ in range(3): s.consume("ip2", 3, 60)
        assert s.consume("ip2", 3, 60) is False

    def test_clear_resets(self):
        s = self._store()
        for _ in range(3): s.consume("ip3", 3, 60)
        s.clear("ip3")
        assert s.consume("ip3", 3, 60) is True

    def test_record_failure_and_lockout(self):
        s = self._store()
        for _ in range(6): s.record_failure("attacker")
        assert s.is_locked_out("attacker", 5, 3600, 0.001) is True

    def test_not_locked_below_threshold(self):
        s = self._store()
        for _ in range(3): s.record_failure("user")
        assert s.is_locked_out("user", 5, 3600, 900) is False

    def test_purge_old_entries(self):
        s = self._store()
        with s._lock:
            s._attempts["k"] = [monotonic() - 100]
        s.consume("k", 5, 10)
        with s._lock:
            assert len(s._attempts["k"]) == 1

    def test_record_failure_caps_at_100(self):
        s = self._store()
        for _ in range(105): s.record_failure("heavy")
        with s._lock:
            assert len(s._attempts["heavy"]) <= 100

    def test_clear_all(self):
        s = self._store()
        s.record_failure("ip1")
        s.clear_all()
        with s._lock:
            assert len(s._attempts) == 0


class TestRateLimitStorePublicAPI:
    def setup_method(self):
        from app.core.rate_limit_store import RateLimitStore
        RateLimitStore.clear_all()

    def test_consume(self):
        from app.core.rate_limit_store import RateLimitStore
        assert RateLimitStore.consume("k", 10, 60) is True

    def test_exceed(self):
        from app.core.rate_limit_store import RateLimitStore
        for _ in range(2): RateLimitStore.consume("k2", 2, 60)
        assert RateLimitStore.consume("k2", 2, 60) is False

    def test_lockout(self):
        from app.core.rate_limit_store import RateLimitStore
        for _ in range(6): RateLimitStore.record_failure("bf")
        assert RateLimitStore.is_locked_out("bf", 5, 3600, 0.001) is True

    def test_clear_key(self):
        from app.core.rate_limit_store import RateLimitStore
        for _ in range(3): RateLimitStore.consume("kc", 2, 60)
        RateLimitStore.clear("kc")
        assert RateLimitStore.consume("kc", 2, 60) is True


# =============================================================================
# 10. app.core.request_state
# =============================================================================

class TestRequestState:
    def setup_method(self):
        from app.core.request_state import _request_state
        self._tok = _request_state.set(None)

    def teardown_method(self):
        from app.core.request_state import _request_state
        try: _request_state.reset(self._tok)
        except Exception: pass

    def test_push_and_get(self):
        from app.core.request_state import push_request_state, get_request_state
        push_request_state(user="alice")
        assert get_request_state().user == "alice"

    def test_get_default_none(self):
        from app.core.request_state import get_request_state
        assert get_request_state() is None

    def test_ensure_creates_if_none(self):
        from app.core.request_state import ensure_request_state, get_request_state
        assert get_request_state() is None
        assert ensure_request_state() is not None

    def test_ensure_returns_existing(self):
        from app.core.request_state import push_request_state, ensure_request_state
        push_request_state(x=1)
        assert ensure_request_state().x == 1

    def test_set_and_get_value(self):
        from app.core.request_state import set_state_value, get_state_value
        set_state_value("uid", 42)
        assert get_state_value("uid") == 42

    def test_get_value_missing(self):
        from app.core.request_state import get_state_value
        assert get_state_value("nope") is None

    def test_get_value_with_default(self):
        from app.core.request_state import get_state_value
        assert get_state_value("x", default="fb") == "fb"

    def test_get_value_no_state(self):
        from app.core.request_state import get_state_value
        assert get_state_value("any") is None

    def test_reset(self):
        from app.core.request_state import push_request_state, reset_request_state, get_request_state
        tok = push_request_state(x=99)
        reset_request_state(tok)
        assert get_request_state() is None

    def test_get_current_request_no_state(self):
        from app.core.request_state import get_current_request
        with pytest.raises(RuntimeError, match="No active request context"):
            get_current_request()

    def test_get_current_request_no_attr(self):
        from app.core.request_state import push_request_state, get_current_request
        push_request_state(user="bob")
        with pytest.raises(RuntimeError): get_current_request()

    def test_get_current_request_none(self):
        from app.core.request_state import push_request_state, get_current_request
        push_request_state(request=None)
        with pytest.raises(RuntimeError): get_current_request()

    def test_get_current_request_ok(self):
        from app.core.request_state import push_request_state, get_current_request
        fake = MagicMock()
        push_request_state(request=fake)
        assert get_current_request() is fake


# =============================================================================
# 11. app.core.runtime_paths
# =============================================================================

class TestRuntimePaths:
    def test_paths_attributes(self):
        from app.core.runtime_paths import paths
        for attr in ("app_data_dir", "backup_dir", "log_dir", "report_dir",
                     "notes_dir", "pdf_reader_dir", "import_dir", "templates_dir", "static_dir"):
            assert hasattr(paths, attr)

    def test_ensure_runtime_dirs(self):
        from app.core.runtime_paths import ensure_runtime_dirs
        with patch.object(Path, "mkdir") as mock_mkdir:
            ensure_runtime_dirs()
            assert mock_mkdir.call_count >= 6
            mock_mkdir.assert_called_with(parents=True, exist_ok=True)


# =============================================================================
# 12. app.core.registry
# =============================================================================

class TestRegistry:
    def setup_method(self):
        from app.core import registry, permissions
        registry._modules.clear()
        permissions._dynamic_permissions_cache = None

    def test_register_descriptor(self):
        from app.core.registry import register, get_module, ModuleDescriptor
        register(ModuleDescriptor(name="m1", label="M1"))
        assert get_module("m1").label == "M1"

    def test_register_module_base(self):
        from app.core.registry import register, get_module
        from app.modules.base import ModuleBase
        class M(ModuleBase):
            @property
            def name(self): return "mb"
        register(M())
        assert get_module("mb") is not None

    def test_register_invalid_raises(self):
        from app.core.registry import register
        with pytest.raises(TypeError): register("invalid")

    def test_get_module_missing(self):
        from app.core.registry import get_module
        assert get_module("nope") is None

    def test_get_all_sorted(self):
        from app.core.registry import register, get_all_modules, ModuleDescriptor
        register(ModuleDescriptor(name="z", label="Z", nav_order=200))
        register(ModuleDescriptor(name="a", label="A", nav_order=10))
        names = [m.name for m in get_all_modules()]
        assert names.index("a") < names.index("z")

    def test_get_enabled_filters_disabled(self):
        from app.core.registry import register, get_enabled_modules, ModuleDescriptor
        register(ModuleDescriptor(name="on", label="On", enabled=True))
        register(ModuleDescriptor(name="off", label="Off", enabled=False))
        enabled = [m.name for m in get_enabled_modules()]
        assert "on" in enabled and "off" not in enabled

    def test_get_module_permissions(self):
        from app.core.registry import register, get_module_permissions, ModuleDescriptor
        register(ModuleDescriptor(name="pm", label="PM", permissions=["p.r", "p.w"]))
        assert "p.r" in get_module_permissions()

    def test_discover_nonexistent_dir(self):
        from app.core.registry import discover_modules
        discover_modules(Path("/nonexistent/path/xyz"))  # No raise

    def test_mount_api_routes(self):
        from app.core.registry import register, mount_api_routes, ModuleDescriptor
        from fastapi import APIRouter
        register(ModuleDescriptor(name="api_m", label="API", api_router=APIRouter(), enabled=True))
        assert mount_api_routes(APIRouter()) >= 1

    def test_descriptor_from_module(self):
        from app.core.registry import ModuleDescriptor
        from app.modules.base import ModuleBase
        class M(ModuleBase):
            @property
            def name(self): return "mm"
            @property
            def permissions(self): return ["m.r"]
        desc = ModuleDescriptor.from_module(M())
        assert desc.name == "mm" and "m.r" in desc.permissions


# =============================================================================
# 13. app.modules.base
# =============================================================================

class TestModuleBase:
    def _mod(self, name="test"):
        from app.modules.base import ModuleBase
        class C(ModuleBase):
            @property
            def name(self): return name
        return C()

    def test_default_label(self):   assert self._mod("expenses").label == "Expenses"
    def test_default_icon(self):    assert self._mod().icon == "bi-box"
    def test_default_nav_order(self): assert self._mod().nav_order == 100
    def test_web_router_none(self): assert self._mod().web_router is None
    def test_api_router_none(self): assert self._mod().api_router is None
    def test_schema_sql_empty(self): assert self._mod().schema_sql == []
    def test_permissions_empty(self): assert self._mod().permissions == []
    def test_role_permissions_empty(self): assert self._mod().role_permissions == {}


# =============================================================================
# 14. app.services.platform_service
# =============================================================================

class TestPlatformService:
    def test_is_desktop(self):
        from app.services.platform_service import PlatformService
        with patch("app.services.platform_service.settings") as s:
            s.desktop_mode = True
            assert PlatformService.is_desktop() is True
            s.desktop_mode = False
            assert PlatformService.is_desktop() is False

    def test_is_server(self):
        from app.services.platform_service import PlatformService
        with patch("app.services.platform_service.settings") as s:
            s.desktop_mode = False
            assert PlatformService.is_server() is True
            s.desktop_mode = True
            assert PlatformService.is_server() is False

    def test_should_apply_strict_csp(self):
        from app.services.platform_service import PlatformService
        with patch("app.services.platform_service.settings") as s:
            s.strict_csp = True; s.desktop_mode = False
            assert PlatformService.should_apply_strict_csp() is True
            s.desktop_mode = True
            assert PlatformService.should_apply_strict_csp() is False
            s.strict_csp = False; s.desktop_mode = False
            assert PlatformService.should_apply_strict_csp() is False


# =============================================================================
# 15. app.core.events
# =============================================================================

class TestEvents:
    def setup_method(self):
        from app.core import events
        events._listeners.clear()

    def teardown_method(self):
        from app.core import events
        events._listeners.clear()
        for pattern, handler in [
            ("*", events._auto_audit), ("*", events._auto_activity),
            ("create.*", events._auto_backup), ("update.*", events._auto_backup),
            ("delete.*", events._auto_backup), ("create.*", events._auto_websocket),
            ("update.*", events._auto_websocket), ("delete.*", events._auto_websocket),
            ("create.*", events._auto_refresh_balances), ("update.*", events._auto_refresh_balances),
            ("delete.*", events._auto_refresh_balances),
        ]:
            events.on(pattern, handler)

    def test_domain_event_creation(self):
        from app.core.events import DomainEvent
        evt = DomainEvent(action="create", entity_type="client", entity_id=1, label="Test")
        assert evt.action == "create" and evt.entity_id == 1

    def test_domain_event_defaults(self):
        from app.core.events import DomainEvent
        evt = DomainEvent(action="delete", entity_type="sale")
        assert evt.entity_id is None and evt.source == "web" and evt.extra == {}

    def test_worker_id_is_hex(self):
        from app.core.events import WORKER_ID
        assert isinstance(WORKER_ID, str) and len(WORKER_ID) == 32

    def test_on_registers(self):
        from app.core.events import on, _listeners
        h = MagicMock()
        on("create.client", h)
        assert h in _listeners["create.client"]

    def test_off_removes(self):
        from app.core.events import on, off, _listeners
        h = MagicMock()
        on("update.sale", h)
        off("update.sale", h)
        assert h not in _listeners["update.sale"]

    def test_off_nonexistent_no_error(self):
        from app.core.events import off
        off("none.pattern", MagicMock())

    def test_emit_exact_match(self):
        from app.core.events import on, emit, DomainEvent
        h = MagicMock()
        on("create.item", h)
        evt = DomainEvent(action="create", entity_type="item")
        emit(evt)
        h.assert_called_once_with(evt)

    def test_emit_wildcard(self):
        from app.core.events import on, emit, DomainEvent
        h = MagicMock()
        on("*", h)
        evt = DomainEvent(action="delete", entity_type="product")
        emit(evt)
        h.assert_called_once_with(evt)

    def test_emit_action_wildcard(self):
        from app.core.events import on, emit, DomainEvent
        h = MagicMock()
        on("create.*", h)
        emit(DomainEvent(action="create", entity_type="material"))
        h.assert_called_once()

    def test_emit_entity_wildcard(self):
        from app.core.events import on, emit, DomainEvent
        h = MagicMock()
        on("*.client", h)
        emit(DomainEvent(action="update", entity_type="client"))
        h.assert_called_once()

    def test_handler_exception_no_propagate(self):
        from app.core.events import on, emit, DomainEvent
        on("*", lambda evt: (_ for _ in ()).throw(RuntimeError("crash")))
        emit(DomainEvent(action="create", entity_type="test"))  # must not raise

    def test_skip_default_handlers(self):
        from app.core.events import on, _trigger_local_handlers, DomainEvent
        called = []
        def _auto_audit(evt): called.append("audit")
        def custom(evt): called.append("custom")
        on("*", _auto_audit); on("*", custom)
        _trigger_local_handlers(DomainEvent(action="create", entity_type="sale"), skip_default=True)
        assert "custom" in called and "audit" not in called

    def test_shutdown_no_scheduler(self):
        from app.core import events
        orig = events.scheduler
        events.scheduler = None
        events.shutdown()
        events.scheduler = orig

    def test_shutdown_scheduler_not_running(self):
        from app.core import events
        if events.scheduler is None: return
        ms = MagicMock(); ms.running = False
        orig = events.scheduler
        events.scheduler = ms
        events.shutdown()
        ms.shutdown.assert_not_called()
        events.scheduler = orig

    def test_startup_no_scheduler(self):
        from app.core import events
        orig = events.scheduler
        events.scheduler = None
        events.startup()
        events.scheduler = orig

    def test_domain_event_extra(self):
        from app.core.events import DomainEvent
        evt = DomainEvent(action="create", entity_type="sale", extra={"origin": "api"})
        assert evt.extra["origin"] == "api"


# =============================================================================
# 16. app.schemas — validators complets
# =============================================================================

class TestSchemas:
    # LoginRequest
    def test_login_valid(self):
        from app.schemas.auth import LoginRequest
        r = LoginRequest(username="admin", password="1234")
        assert r.username == "admin"

    def test_login_blank_username(self):
        from app.schemas.auth import LoginRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LoginRequest(username="  ", password="1234")

    def test_login_blank_password(self):
        from app.schemas.auth import LoginRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LoginRequest(username="admin", password="   ")

    # ChangePasswordRequest
    def test_change_password_valid(self):
        from app.schemas.auth import ChangePasswordRequest
        r = ChangePasswordRequest(current_password="old", new_password="newpass", confirm_password="newpass")
        assert r.confirm_password == "newpass"

    def test_change_password_mismatch(self):
        from app.schemas.auth import ChangePasswordRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="old", new_password="new", confirm_password="diff")

    # UserCreate
    def test_user_create_strips(self):
        from app.schemas.auth import UserCreate
        assert UserCreate(username="  alice  ", password="1234", role="operator").username == "alice"

    def test_user_create_blank_raises(self):
        from app.schemas.auth import UserCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UserCreate(username="   ", password="1234", role="operator")

    # UserUpdate
    def test_user_update(self):
        from app.schemas.auth import UserUpdate
        u = UserUpdate(role="admin", is_active=True)
        assert u.role == "admin" and u.is_active is True

    def test_user_update_empty(self):
        from app.schemas.auth import UserUpdate
        u = UserUpdate()
        assert u.role is None and u.is_active is None

    # ClientValidationSchema
    def test_client_valid(self):
        from app.schemas.client_validation import ClientValidationSchema
        assert ClientValidationSchema(name="Dupont").name == "Dupont"

    def test_client_blank_name(self):
        from app.schemas.client_validation import ClientValidationSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ClientValidationSchema(name="   ")

    def test_client_credit_none(self):
        from app.schemas.client_validation import ClientValidationSchema
        c = ClientValidationSchema(name="T", opening_credit=None)
        assert c.opening_credit == Decimal("0.0000")

    def test_client_credit_empty(self):
        from app.schemas.client_validation import ClientValidationSchema
        assert ClientValidationSchema(name="T", opening_credit="").opening_credit == Decimal("0.0000")

    def test_client_credit_float(self):
        from app.schemas.client_validation import ClientValidationSchema
        assert ClientValidationSchema(name="T", opening_credit=100.5).opening_credit == Decimal("100.5")

    def test_client_credit_european(self):
        from app.schemas.client_validation import ClientValidationSchema
        assert ClientValidationSchema(name="T", opening_credit="1 500,50").opening_credit == Decimal("1500.50")

    def test_client_credit_negative(self):
        from app.schemas.client_validation import ClientValidationSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ClientValidationSchema(name="T", opening_credit="-10")

    def test_client_credit_invalid(self):
        from app.schemas.client_validation import ClientValidationSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ClientValidationSchema(name="T", opening_credit="abc")

    # PaymentCreateSchema
    def test_payment_schema_valid(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        assert PaymentCreateSchema(client_id=1, amount="500.00").client_id == 1

    def test_payment_schema_no_client(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError): PaymentCreateSchema(client_id=None, amount="100")

    def test_payment_schema_empty_client(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError): PaymentCreateSchema(client_id="", amount="100")

    def test_payment_schema_invalid_client(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError): PaymentCreateSchema(client_id="abc", amount="100")

    def test_payment_schema_no_amount(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError): PaymentCreateSchema(client_id=1, amount=None)

    def test_payment_schema_int_amount(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        assert PaymentCreateSchema(client_id=1, amount=250).amount == Decimal("250")

    def test_payment_schema_european_amount(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        assert PaymentCreateSchema(client_id=1, amount="1 500,50").amount == Decimal("1500.50")

    def test_payment_schema_invalid_amount(self):
        from app.schemas.api_schemas import PaymentCreateSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError): PaymentCreateSchema(client_id=1, amount="abc")

    # PaymentCreate (schemas/payment.py)
    def test_payment_create_valid(self):
        from app.schemas.payment import PaymentCreate
        assert PaymentCreate(client_id=1, amount=Decimal("100"), payment_date="2026-05-31").payment_date == "2026-05-31"

    def test_payment_create_invalid_date(self):
        from app.schemas.payment import PaymentCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError): PaymentCreate(client_id=1, amount=Decimal("100"), payment_date="31/05/2026")

    # ProductionBatchCreate (schemas/production.py)
    def test_production_batch_valid(self):
        from app.schemas.production import ProductionBatchCreate, ProductionBatchItemInput
        b = ProductionBatchCreate(
            finished_product_id=1, output_quantity=Decimal("10"),
            production_date="2026-05-31",
            items=[ProductionBatchItemInput(raw_material_id=1, quantity=Decimal("5"))]
        )
        assert b.production_date == "2026-05-31"

    def test_production_batch_invalid_date(self):
        from app.schemas.production import ProductionBatchCreate, ProductionBatchItemInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ProductionBatchCreate(
                finished_product_id=1, output_quantity=Decimal("10"),
                production_date="bad-date",
                items=[ProductionBatchItemInput(raw_material_id=1, quantity=Decimal("5"))]
            )
