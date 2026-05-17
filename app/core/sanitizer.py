from __future__ import annotations

import html
from typing import Any

def sanitize_string(val: str) -> str:
    """
    Sanitizes a single string to prevent HTML/XSS injection.
    Strips leading/trailing whitespace and escapes HTML characters.
    """
    if not isinstance(val, str):
        return val
    return html.escape(val.strip(), quote=True)

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
