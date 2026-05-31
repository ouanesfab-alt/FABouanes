from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import JSONResponse
from app.core.config import settings

import os

import os
import logging

logger = logging.getLogger("fabouanes.rate_limit")

storage_uri = "memory://"

# Create the limiter
limiter = Limiter(
    key_func=get_remote_address, 
    default_limits=["200/minute"],
    storage_uri=storage_uri,
    enabled=(not settings.desktop_mode) and settings.env != "test"  # Disable in desktop mode and test environments
)

async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        {"error": "Trop de tentatives. Réessayez dans quelques minutes."},
        status_code=429,
        headers={"Retry-After": "60"},
    )
