from __future__ import annotations

from itsdangerous import BadSignature, URLSafeSerializer

from app.core.config import settings


AUTH_COOKIE_NAME = "fabouanes_auth"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.secret_key, salt="fabouanes-auth-cookie")


def build_auth_cookie_value(user_id: int) -> str:
    return _serializer().dumps({"user_id": int(user_id)})


def read_auth_cookie_value(raw_value: str | None) -> int | None:
    if not raw_value:
        return None
    try:
        payload = _serializer().loads(raw_value)
    except BadSignature:
        return None
    try:
        return int(payload.get("user_id", 0) or 0) or None
    except Exception:
        return None
