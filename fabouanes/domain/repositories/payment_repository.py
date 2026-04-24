from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol


class PaymentRepository(Protocol):
    def list_payment_page_context(self, *, page: int, page_size: int) -> dict[str, Any]: ...

    def payment_form_context(self) -> dict[str, Any]: ...

    def get_payment(self, payment_id: int): ...

    def list_clients(self): ...

    def list_open_credit_entries(self) -> Iterable[Mapping[str, Any]]: ...

    def client_exists(self, client_id: int) -> bool: ...

    def create_payment(
        self,
        *,
        client_id: int,
        amount: float,
        payment_date: str,
        notes: str,
        sale_link: str,
        payment_type: str,
    ) -> int: ...

    def reverse_payment_allocations(self, payment_row: Mapping[str, Any]) -> None: ...

    def delete_payment(self, payment_id: int) -> None: ...

    def get_finished_sale_credit_entry_for_payment(self, sale_id: int, restored_amount: float) -> dict[str, Any] | None: ...

    def get_raw_sale_credit_entry_for_payment(self, sale_id: int, restored_amount: float) -> dict[str, Any] | None: ...
