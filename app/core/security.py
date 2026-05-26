from __future__ import annotations

import os
import re
import time
from collections import defaultdict
import threading

from app.core.request_state import get_state_value

class _RlStoreCompat:
    def clear(self):
        from app.core.db_access import execute_db
        try:
            execute_db("DELETE FROM rate_limit_events")
        except Exception:
            pass

_rl_store = _RlStoreCompat()


def consume_rate_limit(key: str, limit: int, window: float) -> bool:
    from app.core.rate_limit_store import RateLimitStore
    return RateLimitStore.consume(key, limit, window)


# Trusted proxy IPs: only trust X-Forwarded-For when the direct client is a known proxy.
# Set FAB_TRUSTED_PROXIES=127.0.0.1,10.0.0.1 to enable proxy trust.
_TRUSTED_PROXIES: frozenset[str] = frozenset(
    p.strip() for p in os.environ.get("FAB_TRUSTED_PROXIES", "").split(",") if p.strip()
)


def client_ip() -> str:
    request = get_state_value("request")
    if request is None:
        return "unknown"
    direct_ip = getattr(getattr(request, "client", None), "host", None) or "unknown"
    # Only trust X-Forwarded-For if the direct connection comes from a known proxy
    if _TRUSTED_PROXIES and direct_ip in _TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip() or direct_ip
    return direct_ip


# Password strength mode: 'pin' (4 digits) or 'password' (8+ chars with complexity)
_PASSWORD_MODE = os.environ.get("FAB_PASSWORD_MODE", "pin").strip().lower()


def validate_password_strength(password: str, mode: str | None = None) -> tuple[bool, str]:
    """Validate password strength.

    Modes:
        'pin'      -- Exactly 4 digits (default, backward-compatible)
        'password' -- Minimum 8 characters with at least one letter and one digit
    """
    effective_mode = mode or _PASSWORD_MODE
    p = str(password or "").strip()

    if effective_mode == "password":
        if len(p) < 8:
            return False, "Le mot de passe doit contenir au moins 8 caractères."
        if not re.search(r"[a-zA-Z]", p):
            return False, "Le mot de passe doit contenir au moins une lettre."
        if not re.search(r"\d", p):
            return False, "Le mot de passe doit contenir au moins un chiffre."
        return True, ""

    # Default: PIN mode
    if not p.isdigit() or len(p) != 4:
        return False, "Le code PIN doit être composé d'exactement 4 chiffres."
    return True, ""


def security_headers(response):
    from app.core.config import settings
    from app.services.platform_service import platform
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

    # Enable HSTS only in non-desktop production environments
    if settings.env == "production" and platform.is_server():
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")

    nonce = get_state_value("csp_nonce")
    if platform.should_apply_strict_csp() and nonce:
        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            f"img-src 'self' data: blob:; "
            f"connect-src 'self';"
        )
    else:
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self';"
        )
    response.headers["Content-Security-Policy"] = csp
    return response


# Lockout brute-force mechanism with exponential backoff
_LOGIN_FAILURES = _RlStoreCompat()
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 600
LOCKOUT_DURATION_SECONDS = 900


def is_locked_out(ip: str) -> bool:
    from app.core.rate_limit_store import RateLimitStore
    return RateLimitStore.is_locked_out(ip, LOCKOUT_MAX_ATTEMPTS, LOCKOUT_WINDOW_SECONDS, LOCKOUT_DURATION_SECONDS)


def record_login_failure(ip: str) -> None:
    from app.core.rate_limit_store import RateLimitStore
    RateLimitStore.record_failure(ip)


def clear_login_failures(ip: str) -> None:
    from app.core.rate_limit_store import RateLimitStore
    RateLimitStore.clear(ip)
