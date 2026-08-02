from __future__ import annotations

import secrets
from types import SimpleNamespace

from fastapi import Request
from starlette.datastructures import FormData, UploadFile
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from app.core.request_state import push_request_state, reset_request_state, set_state_value
from app.core.sanitizer import sanitize_string
from app.core.security import security_headers
from app.web.deps import ensure_csrf_token, load_user_from_session


import mimetypes
import os
from pathlib import Path
from starlette.responses import Response

_RAM_STATIC_CACHE: dict[str, tuple[bytes, str]] = {}
_MAX_RAM_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per static file limit


def preload_static_files(directory: str | Path) -> int:
    """Pre-load all static assets into RAM memory for instant zero-disk-latency serving."""
    root = Path(directory)
    if not root.exists():
        return 0
    count = 0
    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.stat().st_size <= _MAX_RAM_FILE_SIZE:
            rel_path = str(file_path.relative_to(root)).replace("\\", "/")
            try:
                content = file_path.read_bytes()
                media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                _RAM_STATIC_CACHE[rel_path] = (content, media_type)
                count += 1
            except Exception:
                pass
    return count


class CachedStaticFiles(StaticFiles):
    def is_not_modified(self, response_headers, request_headers) -> bool:
        return super().is_not_modified(response_headers, request_headers)

    async def get_response(self, path: str, scope):
        cached = _RAM_STATIC_CACHE.get(path)
        if cached:
            content, media_type = cached
            res = Response(content=content, media_type=media_type)
            res.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
            return res

        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
            try:
                full_path = self.get_path(path)
                if full_path and os.path.isfile(full_path) and os.path.getsize(full_path) <= _MAX_RAM_FILE_SIZE:
                    with open(full_path, "rb") as f:
                        _RAM_STATIC_CACHE[path] = (f.read(), response.media_type or "application/octet-stream")
            except Exception:
                pass
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/static/"):
            response = await call_next(request)
            return security_headers(response)

        # Inject transparent global XSS sanitization on request.form for form types only
        content_type = request.headers.get("content-type", "")
        is_form = "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type

        if is_form:
            original_form = request.form
            async def sanitized_form():
                form_data = await original_form()
                cleaned_items = []
                for k, v in form_data.multi_items():
                    if isinstance(v, UploadFile):
                        cleaned_items.append((k, v))
                    elif "password" in k.lower():
                        cleaned_items.append((k, v))
                    else:
                        cleaned_items.append((k, sanitize_string(v)))
                return FormData(cleaned_items)
            request.form = sanitized_form

        csp_nonce = secrets.token_hex(16)
        token = push_request_state(
            request=request,
            db=None,  # Lazily created on demand via db_manager
            session=request.session,
            request_id=secrets.token_hex(12),
            audit_source="api" if request.url.path.startswith("/api/v1/") else "web",
            user=None,
            g=SimpleNamespace(user=None),
            csp_nonce=csp_nonce,
        )
        try:
            ensure_csrf_token(request)
            user = load_user_from_session(request)
            request.state.user = user
            set_state_value("user", user)
            set_state_value("g", SimpleNamespace(user=user))
            response = await call_next(request)
        finally:
            try:
                from app.core.request_state import get_request_state
                state = get_request_state()
                if state is not None:
                    write_db = getattr(state, "db", None)
                    if write_db is not None:
                        try:
                            write_db.close()
                        except Exception:
                            pass
                    read_db = getattr(state, "read_db", None)
                    if read_db is not None:
                        try:
                            read_db.close()
                        except Exception:
                            pass
            except Exception:
                pass
            reset_request_state(token)
        return security_headers(response)
