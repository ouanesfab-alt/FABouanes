from __future__ import annotations

import re
import secrets
import time
from collections import defaultdict
from fabouanes.fastapi_compat import abort, jsonify, request, session

_rl_store: dict[str, list[float]] = defaultdict(list)


def _prune(key: str, window: float) -> list[float]:
    now = time.time()
    hits = [t for t in _rl_store.get(key, []) if now - t < window]
    _rl_store[key] = hits
    return hits


def consume_rate_limit(key: str, limit: int, window: float) -> bool:
    hits = _prune(key, window)
    if len(hits) >= limit:
        return False
    hits.append(time.time())
    _rl_store[key] = hits
    return True


def client_ip() -> str:
    return request.remote_addr or "unknown"


def validate_password_strength(password: str) -> tuple[bool, str]:
    normalized = str(password or "").strip()
    if not re.fullmatch(r"\d{4}", normalized):
        return False, "Le mot de passe doit contenir exactement 4 chiffres."
    return True, ""


def security_headers(response):
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    csp = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:; img-src 'self' data: blob: https:; connect-src 'self' https:;"
    response.headers.setdefault("Content-Security-Policy", csp)
    return response


def ensure_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


def csrf_protect():
    if request.method != "POST":
        return
    if request.endpoint in {"static"}:
        return
    if request.path.startswith("/api/v1/"):
        return
    token = session.get("csrf_token")
    supplied = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.headers.get("X-Csrf-Token")
    )
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        supplied = supplied or payload.get("csrf_token")
    else:
        supplied = supplied or request.form.get("csrf_token")
    if not token or not supplied or token != supplied:
        abort(400, description="CSRF token invalide.")


def jsonify_rate_limited(message: str = "Trop de requêtes. Réessaie dans quelques instants."):
    return jsonify({"ok": False, "error": message}), 429
