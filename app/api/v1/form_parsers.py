from __future__ import annotations

from typing import Any
from starlette.datastructures import FormData

def payload_to_form_data(payload: dict[str, Any]) -> FormData:
    items: list[tuple[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, list):
            for item in value:
                items.append((key, item))
        else:
            items.append((key, value))
    return FormData(items)
