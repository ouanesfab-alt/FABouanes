from __future__ import annotations

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import db_transaction
from fabouanes.core.perf_cache import cached_result
from fabouanes.core.storage import backup_database
from fabouanes.application.use_cases.payment_use_cases import PaymentUseCases
from fabouanes.infrastructure.repositories.payment_repository import DbPaymentRepository
from fabouanes.presentation.schemas import build_payment_command


_PAYMENT_USE_CASES = PaymentUseCases(
    repository=DbPaymentRepository(),
    transaction_factory=db_transaction,
    log_activity=log_activity,
    audit_event=audit_event,
    backup_database=backup_database,
)


def payments_context(*, page: int, page_size: int):
    return cached_result(
        ("payments_context", int(page), int(page_size)),
        lambda: _PAYMENT_USE_CASES.payments_context(page=page, page_size=page_size),
        ttl_seconds=8.0,
    )


def new_payment_context():
    return _PAYMENT_USE_CASES.new_payment_context()


def create_payment_from_form(form):
    return _PAYMENT_USE_CASES.create_payment(build_payment_command(form))


def get_edit_payment_context(payment_id: int):
    return _PAYMENT_USE_CASES.get_edit_payment_context(payment_id)


def edit_payment_from_form(payment_id: int, form):
    return _PAYMENT_USE_CASES.edit_payment(payment_id, build_payment_command(form))


def delete_payment_by_id(payment_id: int) -> bool:
    return _PAYMENT_USE_CASES.delete_payment(payment_id)
