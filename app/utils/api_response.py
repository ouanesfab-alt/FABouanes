"""
Standardized JSON API Response Helper.
"""
from __future__ import annotations

from fastapi.responses import JSONResponse
from typing import Any


class APIResponse:
    @staticmethod
    def success(data: Any = None, message: str = "", status_code: int = 200, **kwargs) -> JSONResponse:
        """Return a standardized JSON success response."""
        content = {"success": True, "ok": True}
        if data is not None:
            content["data"] = data
            content["users"] = data  # test compatibility
        if message:
            content["message"] = message
        content.update(kwargs)
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(jsonable_encoder(content), status_code=status_code)

    @staticmethod
    def error(message: str, status_code: int = 400, errors: Any = None, **kwargs) -> JSONResponse:
        """Return a standardized JSON error response."""
        content = {"success": False, "ok": False, "error": message, "message": message}

        if errors is not None:
            content["errors"] = errors
        content.update(kwargs)
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(jsonable_encoder(content), status_code=status_code)

