from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.services.platform_service import platform

# Create the limiter
limiter = Limiter(
    key_func=get_remote_address, 
    default_limits=["200/minute"],
    enabled=platform.is_server() and settings.env != "test"  # Disable in desktop mode and test environments
)

async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        {"error": "Trop de tentatives. Réessayez dans quelques minutes."},
        status_code=429,
        headers={"Retry-After": "60"},
    )
