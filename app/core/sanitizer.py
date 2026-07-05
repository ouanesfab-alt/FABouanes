from __future__ import annotations

import html
import os
from typing import Any

MAX_INPUT_LENGTH = int(os.environ.get("FAB_MAX_INPUT_LENGTH", "65536") or "65536")

def sanitize_string(val: str) -> str:
    """
    Sanitizes a single string to prevent HTML/XSS injection.
    Strips leading/trailing whitespace and escapes HTML characters.
    Truncates the string if it exceeds MAX_INPUT_LENGTH to prevent memory exhaustion.
    """
    if not isinstance(val, str):
        return val
    cleaned = val.strip()
    if len(cleaned) > MAX_INPUT_LENGTH:
        cleaned = cleaned[:MAX_INPUT_LENGTH] + "... [TRUNCATED]"
    return html.escape(cleaned, quote=True)

def sanitize_input(data: Any) -> Any:
    """
    Recursively sanitizes input data (str, dict, list, tuple) to clean all string inputs.
    Useful for sanitizing request JSON payloads or form data.
    """
    if isinstance(data, str):
        return sanitize_string(data)
    elif isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [sanitize_input(i) for i in data]
    return data
