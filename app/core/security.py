from __future__ import annotations

import re
import time
from collections import defaultdict
import threading

from app.core.request_state import get_state_value

_rl_store: dict[str, list[float]] = defaultdict(list)
_rl_lock = threading.Lock()


def _prune(key: str, window: float) -> list[float]:
    now = time.time()
    hits = [hit for hit in _rl_store.get(key, []) if now - hit < window]
    _rl_store[key] = hits
    return hits


def consume_rate_limit(key: str, limit: int, window: float) -> bool:
    with _rl_lock:
        hits = _prune(key, window)
        if len(hits) >= limit:
            return False
        hits.append(time.time())
        _rl_store[key] = hits
        return True


def client_ip() -> str:
    request = get_state_value("request")
    if request is None:
        return "unknown"
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return getattr(getattr(request, "client", None), "host", None) or "unknown"


def validate_password_strength(password: str) -> tuple[bool, str]:
    p = str(password or "").strip()
    if not p.isdigit() or len(p) != 4:
        return False, "Le code PIN doit être composé d'exactement 4 chiffres."
    return True, ""


def security_headers(response):
    from app.core.config import settings
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    
    # Enable HSTS only in non-desktop production environments
    if settings.env == "production" and not settings.desktop_mode:
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")

    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self';"
    )
    response.headers["Content-Security-Policy"] = csp
    return response


# Lockout brute-force mechanism
_LOGIN_FAILURES: dict[str, list[float]] = defaultdict(list)
_LOGIN_LOCK = threading.Lock()
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 600
LOCKOUT_DURATION_SECONDS = 900


def is_locked_out(ip: str) -> bool:
    with _LOGIN_LOCK:
        hits = [h for h in _LOGIN_FAILURES.get(ip, []) if time.time() - h < LOCKOUT_WINDOW_SECONDS]
        _LOGIN_FAILURES[ip] = hits
        return len(hits) >= LOCKOUT_MAX_ATTEMPTS


def record_login_failure(ip: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES[ip].append(time.time())


def clear_login_failures(ip: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.pop(ip, None)
