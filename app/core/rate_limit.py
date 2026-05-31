from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.services.platform_service import platform

import os

import os
import logging

logger = logging.getLogger("fabouanes.rate_limit")

redis_url = os.environ.get("REDIS_URL", "").strip()
storage_uri = "memory://"

if redis_url:
    try:
        import redis
        # Verify if Redis is reachable with a short timeout
        client = redis.from_url(redis_url, socket_connect_timeout=1.0, socket_timeout=1.0)
        client.ping()
        storage_uri = redis_url
        logger.info("Rate limiter successfully connected to Redis storage.")
    except Exception as e:
        logger.warning("Rate limiter failed to connect to Redis (%s): %s. Falling back to memory:// storage.", redis_url, e)
        storage_uri = "memory://"

# Create the limiter
limiter = Limiter(
    key_func=get_remote_address, 
    default_limits=["200/minute"],
    storage_uri=storage_uri,
    enabled=platform.is_server() and settings.env != "test"  # Disable in desktop mode and test environments
)

async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        {"error": "Trop de tentatives. Réessayez dans quelques minutes."},
        status_code=429,
        headers={"Retry-After": "60"},
    )
