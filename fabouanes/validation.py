from __future__ import annotations

from datetime import datetime, date

def clean_text(value: str, max_length: int = 255) -> str:
    return (value or "").strip()[:max_length]

def require_positive_number(value, field_name: str) -> tuple[bool, float, str]:
    try:
        number = float(value)
    except Exception:
        return False, 0.0, f"{field_name} invalide."
    if number < 0:
        return False, number, f"{field_name} doit être positif."
    return True, number, ""

def normalize_date(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return date.today().isoformat()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except Exception:
        return date.today().isoformat()
