from __future__ import annotations

import os
import re
import time
from collections import defaultdict
import threading

from app.core.request_state import get_state_value

_rl_store: dict[str, list[float]] = defaultdict(list)
_rl_lock = threading.Lock()
_rl_last_cleanup = 0.0
_RL_CLEANUP_INTERVAL = 300.0  # Prune stale entries every 5 minutes


def _prune(key: str, window: float) -> list[float]:
    now = time.time()
    hits = [hit for hit in _rl_store.get(key, []) if now - hit < window]
    _rl_store[key] = hits
    return hits


def _cleanup_stale_entries(window: float) -> None:
    """Remove keys with no recent hits to prevent unbounded memory growth."""
    global _rl_last_cleanup
    now = time.time()
    if now - _rl_last_cleanup < _RL_CLEANUP_INTERVAL:
        return
    _rl_last_cleanup = now
    stale_keys = [k for k, v in _rl_store.items() if not v or now - max(v) >= window]
    for k in stale_keys:
        _rl_store.pop(k, None)


def consume_rate_limit(key: str, limit: int, window: float) -> bool:
    with _rl_lock:
        hits = _prune(key, window)
        if len(hits) >= limit:
            return False
        hits.append(time.time())
        _rl_store[key] = hits
        _cleanup_stale_entries(window)
        return True


def client_ip() -> str:
    request = get_state_value("request")
    if request is None:
        return "unknown"
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return getattr(getattr(request, "client", None), "host", None) or "unknown"


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
_LOGIN_FAILURES: dict[str, list[float]] = defaultdict(list)
_LOGIN_LOCK = threading.Lock()
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 600
LOCKOUT_DURATION_SECONDS = 900


def is_locked_out(ip: str) -> bool:
    with _LOGIN_LOCK:
        hits = [h for h in _LOGIN_FAILURES.get(ip, []) if time.time() - h < LOCKOUT_WINDOW_SECONDS]
        _LOGIN_FAILURES[ip] = hits
        if len(hits) >= LOCKOUT_MAX_ATTEMPTS:
            # Exponential backoff: lock longer for repeated offenders
            extra_attempts = len(hits) - LOCKOUT_MAX_ATTEMPTS
            lockout_time = LOCKOUT_DURATION_SECONDS * (2 ** min(extra_attempts, 4))
            last_failure = max(hits) if hits else 0
            return (time.time() - last_failure) < lockout_time
        return False


def record_login_failure(ip: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES[ip].append(time.time())


def clear_login_failures(ip: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.pop(ip, None)
