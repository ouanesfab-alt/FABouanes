"""
Utility formatting functions for currency and numeric conversions.
"""

from __future__ import annotations


def to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def format_dzd(amount: float | int | str | None) -> str:
    """Formats monetary amounts into clean Dinar Algérien currency representation (ex: 125 450,00 DA)."""
    try:
        val = float(str(amount or 0).replace(",", "."))
        formatted = f"{val:,.2f}".replace(",", " ").replace(".", ",")
        return f"{formatted} DA"
    except Exception:
        return "0,00 DA"
