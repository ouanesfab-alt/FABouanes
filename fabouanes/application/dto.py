from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaymentCommandDTO:
    client_id: int
    sale_link: str
    amount: float
    payment_date: str
    payment_type: str
    notes: str

