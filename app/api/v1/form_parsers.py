from __future__ import annotations

from typing import Any
from starlette.datastructures import FormData

def payload_to_form_data(payload: dict[str, Any]) -> FormData:
    items: list[tuple[str, str]] = []
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, list):
            for item in value:
                if item is not None:
                    items.append((key, str(item)))
        else:
            if isinstance(value, bool):
                items.append((key, "1" if value else "0"))
            else:
                items.append((key, str(value)))
    return FormData(items)
