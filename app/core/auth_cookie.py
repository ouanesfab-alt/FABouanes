from __future__ import annotations

from itsdangerous import BadSignature, URLSafeSerializer

from app.core.config import settings

AUTH_COOKIE_NAME = "fabouanes_auth"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.secret_key, salt="fabouanes-auth-cookie")


def build_auth_cookie_value(
    user_id: int,
    fingerprint: str | None = None,
    max_age: int | None = None,
    auth_time: int | None = None,
) -> str:
    import time

    now = int(time.time())
    ttl = int(max_age) if max_age is not None else 86400
    payload = {
        "user_id": int(user_id),
        "auth_time": auth_time or now,
        "exp": now + ttl,
    }
    if fingerprint:
        payload["fingerprint"] = fingerprint
    return _serializer().dumps(payload)


def read_auth_cookie_payload(raw_value: str | None, current_fingerprint: str | None = None) -> dict | None:
    if not raw_value:
        return None
    try:
        payload = _serializer().loads(raw_value)
    except BadSignature:
        return None
    try:
        import time

        now = int(time.time())
        exp = payload.get("exp")
        if exp is not None and now > int(exp):
            return None
        if current_fingerprint and "fingerprint" in payload:
            if payload["fingerprint"] != current_fingerprint:
                return None
        if not int(payload.get("user_id", 0) or 0):
            return None
        return payload
    except Exception:
        return None


def read_auth_cookie_value(raw_value: str | None, current_fingerprint: str | None = None) -> int | None:
    payload = read_auth_cookie_payload(raw_value, current_fingerprint)
    if payload:
        return int(payload["user_id"])
    return None
