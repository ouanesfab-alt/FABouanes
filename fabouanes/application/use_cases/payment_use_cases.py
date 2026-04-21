from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from fabouanes.application.dto import PaymentCommandDTO
from fabouanes.domain.exceptions import NotFoundError, ValidationError
from fabouanes.domain.repositories.payment_repository import PaymentRepository


@dataclass(slots=True)
class PaymentUseCases:
    repository: PaymentRepository
    transaction_factory: Callable[[], AbstractContextManager[Any]]
    log_activity: Callable[[str, str, int, str], None]
    audit_event: Callable[..., None]
    backup_database: Callable[[str], None]

    def payments_context(self) -> dict[str, Any]:
        return self.repository.list_payment_page_context()

    def new_payment_context(self) -> dict[str, Any]:
        return self.repository.payment_form_context()

    def get_edit_payment_context(self, payment_id: int) -> dict[str, Any] | None:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            return None

        current_link = ""
        if payment["sale_kind"] == "finished" and payment["sale_id"]:
            current_link = f"finished:{payment['sale_id']}"
        elif payment["sale_kind"] == "raw" and payment["raw_sale_id"]:
            current_link = f"raw:{payment['raw_sale_id']}"

        open_sales = list(self.repository.list_open_credit_entries())
        existing_keys = [f"{sale['item_kind']}:{sale['id']}" for sale in open_sales]
        if current_link and current_link not in existing_keys:
            restored_sale = self._restored_sale_entry(payment)
            if restored_sale:
                open_sales.append(restored_sale)

        return {
            "payment": payment,
            "current_link": current_link,
            "clients": self.repository.list_clients(),
            "open_sales": open_sales,
        }

    def create_payment(self, command: PaymentCommandDTO) -> tuple[int, str]:
        self._ensure_client_exists(command.client_id)
        payment_id = self._create_payment(command)
        created = self.repository.get_payment(payment_id)
        self.log_activity(
            "create_payment",
            "payment",
            payment_id,
            f"client #{command.client_id} {command.payment_type} montant={command.amount}",
        )
        self.audit_event("create_payment", "payment", payment_id, after=created)
        self.backup_database("create_payment")
        return payment_id, command.payment_type

    def edit_payment(self, payment_id: int, command: PaymentCommandDTO) -> int:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise NotFoundError("Versement introuvable.")

        self._ensure_client_exists(command.client_id)
        before = dict(payment)
        with self.transaction_factory():
            self.repository.reverse_payment_allocations(payment)
            self.repository.delete_payment(payment_id)
            new_payment_id = self._create_payment(command)
        after = self.repository.get_payment(new_payment_id)
        self.log_activity(
            "update_payment",
            "payment",
            payment_id,
            f"client #{command.client_id} {command.payment_type} montant={command.amount}",
        )
        self.audit_event("update_payment", "payment", payment_id, before=before, after=after)
        self.backup_database("update_payment")
        return new_payment_id

    def delete_payment(self, payment_id: int) -> bool:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            return False

        before = dict(payment)
        with self.transaction_factory():
            self.repository.reverse_payment_allocations(payment)
            self.repository.delete_payment(payment_id)

        self.log_activity("delete_payment", "payment", payment_id, "Suppression transaction client")
        self.audit_event("delete_payment", "payment", payment_id, before=before, after=None)
        self.backup_database("delete_payment")
        return True

    def _ensure_client_exists(self, client_id: int) -> None:
        if not self.repository.client_exists(client_id):
            raise ValidationError("Client introuvable.")

    def _create_payment(self, command: PaymentCommandDTO) -> int:
        try:
            return self.repository.create_payment(
                client_id=command.client_id,
                amount=command.amount,
                payment_date=command.payment_date,
                notes=command.notes,
                sale_link=command.sale_link,
                payment_type=command.payment_type,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def _restored_sale_entry(self, payment) -> dict[str, Any] | None:
        if payment["sale_kind"] == "finished" and payment["sale_id"]:
            return self.repository.get_finished_sale_credit_entry_for_payment(
                int(payment["sale_id"]),
                float(payment["amount"]),
            )
        if payment["sale_kind"] == "raw" and payment["raw_sale_id"]:
            return self.repository.get_raw_sale_credit_entry_for_payment(
                int(payment["raw_sale_id"]),
                float(payment["amount"]),
            )
        return None
