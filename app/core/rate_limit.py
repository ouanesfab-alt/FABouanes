from fastapi.responses import JSONResponse

from app.core.config import settings

try:
    from slowapi import Limiter

    def _rate_limit_key(request) -> str:
        from app.core.security import client_ip

        return client_ip(request)

    limiter = Limiter(
        key_func=_rate_limit_key,
        default_limits=["200/minute"],
        storage_uri="memory://",
        enabled=(not settings.desktop_mode) and settings.env != "test",
    )
except Exception:

    class DummyLimiter:
        def limit(self, *args, **kwargs):
            return lambda func: func

    limiter = DummyLimiter()


async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        {"error": "Trop de tentatives. Réessayez dans quelques minutes."},
        status_code=429,
        headers={"Retry-After": "60"},
    )
