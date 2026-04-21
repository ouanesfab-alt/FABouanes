from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from fabouanes.application.dto import PaymentCommandDTO
from fabouanes.core.helpers import to_float
from fabouanes.domain.exceptions import ValidationError

VALID_PAYMENT_TYPES = {"versement", "avance"}


def build_payment_command(payload: Mapping[str, Any]) -> PaymentCommandDTO:
    client_raw = str(payload.get("client_id") or "").strip()
    if not client_raw:
        raise ValidationError("Choisis un client.")
    try:
        client_id = int(client_raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Choisis un client.") from exc

    payment_type = str(payload.get("payment_type") or "versement").strip().lower() or "versement"
    if payment_type not in VALID_PAYMENT_TYPES:
        payment_type = "versement"

    payment_date = str(payload.get("payment_date") or "").strip() or date.today().isoformat()
    sale_link = str(payload.get("sale_link") or "").strip()
    notes = str(payload.get("notes") or "").strip()

    return PaymentCommandDTO(
        client_id=client_id,
        sale_link=sale_link,
        amount=to_float(payload.get("amount")),
        payment_date=payment_date,
        payment_type=payment_type,
        notes=notes,
    )

