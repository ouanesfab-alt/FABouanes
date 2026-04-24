from __future__ import annotations

import unittest

from fabouanes.presentation.api_validation import (
    AuthLoginPayload,
    PaymentCreatePayload,
    SaleCreatePayload,
    validate_payload,
)


class ApiValidationTests(unittest.TestCase):
    def test_auth_login_payload_requires_username_and_password(self) -> None:
        payload, errors = validate_payload(AuthLoginPayload, {"username": "admin"})
        self.assertEqual(payload, {})
        self.assertIsNotNone(errors)
        assert errors is not None
        self.assertTrue(any(err.get("loc") == ("password",) for err in errors))

    def test_payment_payload_normalizes_invalid_payment_type(self) -> None:
        payload, errors = validate_payload(
            PaymentCreatePayload,
            {"client_id": "1", "amount": "55.0", "payment_type": "INVALID", "payment_date": "2026-01-01"},
        )
        self.assertIsNone(errors)
        self.assertEqual(payload.get("payment_type"), "versement")

    def test_sale_payload_requires_item_key(self) -> None:
        payload, errors = validate_payload(
            SaleCreatePayload,
            {"quantity": "2", "unit_price": "100", "sale_date": "2026-01-01"},
        )
        self.assertEqual(payload, {})
        self.assertIsNotNone(errors)
        assert errors is not None
        self.assertTrue(any(err.get("loc") == ("item_key",) for err in errors))
