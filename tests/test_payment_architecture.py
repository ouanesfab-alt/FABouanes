from __future__ import annotations

from contextlib import nullcontext
from unittest import TestCase

from fabouanes.application.dto import PaymentCommandDTO
from fabouanes.application.use_cases.payment_use_cases import PaymentUseCases
from fabouanes.domain.exceptions import NotFoundError, ValidationError
from fabouanes.presentation.schemas import build_payment_command


class _FakePaymentRepository:
    def __init__(self, *, client_exists: bool = True, payment: dict | None = None):
        self._client_exists = client_exists
        self._payment = payment
        self.deleted_ids: list[int] = []
        self.created_commands: list[dict] = []
        self.reversed_rows: list[dict] = []

    def list_payment_page_context(self):
        return {"payments": []}

    def payment_form_context(self):
        return {"clients": []}

    def get_payment(self, payment_id: int):
        if self._payment and int(self._payment["id"]) == int(payment_id):
            return dict(self._payment)
        if self.created_commands and payment_id == 99:
            return {"id": 99, **self.created_commands[-1]}
        return None

    def list_clients(self):
        return []

    def list_open_credit_entries(self):
        return []

    def client_exists(self, client_id: int) -> bool:
        return self._client_exists

    def create_payment(self, **kwargs):
        self.created_commands.append(kwargs)
        return 99

    def reverse_payment_allocations(self, payment_row):
        self.reversed_rows.append(dict(payment_row))

    def delete_payment(self, payment_id: int):
        self.deleted_ids.append(payment_id)

    def get_finished_sale_credit_entry_for_payment(self, sale_id: int, restored_amount: float):
        return None

    def get_raw_sale_credit_entry_for_payment(self, sale_id: int, restored_amount: float):
        return None


class PaymentArchitectureTests(TestCase):
    def _use_cases(self, repo: _FakePaymentRepository) -> PaymentUseCases:
        return PaymentUseCases(
            repository=repo,
            transaction_factory=nullcontext,
            log_activity=lambda *args, **kwargs: None,
            audit_event=lambda *args, **kwargs: None,
            backup_database=lambda *args, **kwargs: None,
        )

    def test_build_payment_command_requires_client(self) -> None:
        with self.assertRaises(ValidationError):
            build_payment_command({"client_id": "", "amount": "100"})

    def test_build_payment_command_normalizes_invalid_payment_type(self) -> None:
        command = build_payment_command(
            {
                "client_id": "7",
                "amount": "125.5",
                "payment_type": "inconnu",
                "payment_date": "2026-04-21",
                "notes": "Test",
            }
        )

        self.assertEqual(
            command,
            PaymentCommandDTO(
                client_id=7,
                sale_link="",
                amount=125.5,
                payment_date="2026-04-21",
                payment_type="versement",
                notes="Test",
            ),
        )

    def test_edit_payment_rejects_missing_row_before_side_effects(self) -> None:
        repo = _FakePaymentRepository(client_exists=True, payment=None)

        with self.assertRaises(NotFoundError):
            self._use_cases(repo).edit_payment(
                4,
                PaymentCommandDTO(
                    client_id=1,
                    sale_link="",
                    amount=50.0,
                    payment_date="2026-04-21",
                    payment_type="versement",
                    notes="",
                ),
            )

        self.assertEqual(repo.deleted_ids, [])
        self.assertEqual(repo.created_commands, [])

    def test_edit_payment_validates_client_before_deleting_original_row(self) -> None:
        repo = _FakePaymentRepository(
            client_exists=False,
            payment={"id": 4, "sale_kind": "", "sale_id": None, "raw_sale_id": None, "amount": 75.0},
        )

        with self.assertRaises(ValidationError):
            self._use_cases(repo).edit_payment(
                4,
                PaymentCommandDTO(
                    client_id=999,
                    sale_link="",
                    amount=50.0,
                    payment_date="2026-04-21",
                    payment_type="versement",
                    notes="",
                ),
            )

        self.assertEqual(repo.deleted_ids, [])
        self.assertEqual(repo.reversed_rows, [])
