"""Request timeout middleware for FastAPI.

Protects against long-running requests that could hang a worker indefinitely.
Configurable via ``FAB_REQUEST_TIMEOUT_SECONDS`` environment variable (default: 30s).

Routes matching ``EXEMPT_PREFIXES`` get a longer timeout (3×) to accommodate
PDF generation and large report exports.
"""
from __future__ import annotations

import asyncio
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("fabouanes.timeout")

try:
    _DEFAULT_TIMEOUT = max(5.0, min(300.0, float(os.environ.get("FAB_REQUEST_TIMEOUT_SECONDS", "30") or "30")))
except Exception:
    _DEFAULT_TIMEOUT = 30.0

# Routes that need extra time (PDF generation, large exports, backups)
EXEMPT_PREFIXES = ("/print/", "/api/v1/print/", "/api/v1/backup/", "/admin/backup")


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Cancel requests that exceed a configurable timeout.

    Static files and health-check endpoints are excluded entirely.
    Print/backup endpoints receive a 3× multiplier on the timeout.
    """

    def __init__(self, app, *, timeout_seconds: float = _DEFAULT_TIMEOUT):
        super().__init__(app)
        self.timeout = timeout_seconds
        self.long_timeout = timeout_seconds * 3  # For PDF/backup routes

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip timeout for static files and health checks
        if path.startswith("/static/") or path == "/health" or path == "/metrics":
            return await call_next(request)

        # Use longer timeout for heavy operations
        if path.startswith("/assistant/"):
            timeout = 180.0  # Local AI (Ollama) can be slow on CPU
        else:
            timeout = self.long_timeout if any(path.startswith(p) for p in EXEMPT_PREFIXES) else self.timeout

        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(
                "Request timeout after %.1fs: %s %s",
                timeout,
                request.method,
                path,
            )

            # Check if the client expects JSON
            accept = request.headers.get("accept", "")
            if "application/json" in accept or path.startswith("/api/"):
                return JSONResponse(
                    {"success": False, "error": {"code": "timeout", "message": "La requête a pris trop de temps. Veuillez réessayer."}},
                    status_code=504,
                )

            # HTML fallback
            from app.web.deps import template_context, templates
            try:
                return templates.TemplateResponse(
                    "error.html",
                    template_context(request, status_code=504, error_message="La requête a pris trop de temps. Veuillez réessayer."),
                    status_code=504,
                )
            except Exception:
                return JSONResponse(
                    {"success": False, "error": {"code": "timeout", "message": "Délai d'attente dépassé"}},
                    status_code=504,
                )
