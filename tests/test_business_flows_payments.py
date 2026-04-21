from tests.business_flow_case import *  # noqa: F401,F403


class PaymentsBusinessFlowTests(BusinessFlowTestCase):
    def test_deleting_payment_reopens_client_credit(self) -> None:
        client_id = self._create_client()
        product_id = self._create_finished_product(stock_qty=200, sale_price=100, avg_cost=60)
        self._login()

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "10",
                "unit": "kg",
                "unit_price": "100",
                "sale_date": date.today().isoformat(),
                "notes": "Vente a credit",
            },
            preflight_path="/sales",
        )
        sale = self._fetchone("SELECT id FROM sales WHERE client_id = ? ORDER BY id DESC", (client_id,))
        self.assertIsNotNone(sale)

        self._post_form(
            "/payments",
            {
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "400",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement test",
            },
            preflight_path="/payments",
        )
        payment = self._fetchone("SELECT id FROM payments WHERE client_id = ? ORDER BY id DESC", (client_id,))
        self.assertIsNotNone(payment)

        delete_response = self._post_form(
            f"/payments/{int(payment['id'])}/delete",
            {},
            preflight_path="/payments",
        )

        self.assertEqual(delete_response.status_code, 200)
        updated_sale = self._fetchone("SELECT amount_paid, balance_due FROM sales WHERE id = ?", (int(sale["id"]),))
        deleted_payment = self._fetchone("SELECT id FROM payments WHERE id = ?", (int(payment["id"]),))
        self.assertIsNotNone(updated_sale)
        self.assertAlmostEqual(float(updated_sale["amount_paid"]), 0.0)
        self.assertAlmostEqual(float(updated_sale["balance_due"]), 1000.0)
        self.assertIsNone(deleted_payment)

    def test_edit_payment_reallocates_credit_amount(self) -> None:
        client_id = self._create_client()
        product_id = self._create_finished_product(stock_qty=200, sale_price=100, avg_cost=60)
        self._login()

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "10",
                "unit": "kg",
                "unit_price": "100",
                "sale_date": date.today().isoformat(),
                "notes": "Vente credit",
            },
            preflight_path="/sales",
        )
        sale = self._fetchone("SELECT id FROM sales WHERE client_id = ? ORDER BY id DESC", (client_id,))
        self.assertIsNotNone(sale)

        self._post_form(
            "/payments",
            {
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "400",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement initial",
            },
            preflight_path="/payments",
        )
        payment = self._fetchone("SELECT id FROM payments WHERE client_id = ? ORDER BY id DESC", (client_id,))
        self.assertIsNotNone(payment)

        edit_response = self._post_form(
            f"/payments/{int(payment['id'])}/edit",
            {
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "250",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement modifie",
            },
            preflight_path=f"/payments/{int(payment['id'])}/edit",
        )

        self.assertEqual(edit_response.status_code, 200)
        payment_count = self._scalar("SELECT COUNT(*) FROM payments WHERE client_id = ?", (client_id,))
        latest_payment = self._fetchone(
            "SELECT amount, payment_type, allocation_meta FROM payments WHERE client_id = ? ORDER BY id DESC",
            (client_id,),
        )
        updated_sale = self._fetchone("SELECT amount_paid, balance_due FROM sales WHERE id = ?", (int(sale["id"]),))
        self.assertEqual(int(payment_count), 1)
        self.assertAlmostEqual(float(latest_payment["amount"]), 250.0)
        self.assertEqual(str(latest_payment["payment_type"]), "versement")
        self.assertIn('"amount": 250.0', str(latest_payment["allocation_meta"]))
        self.assertAlmostEqual(float(updated_sale["amount_paid"]), 250.0)
        self.assertAlmostEqual(float(updated_sale["balance_due"]), 750.0)

    def test_edit_payment_rollback_keeps_original_payment_when_client_is_invalid(self) -> None:
        client_id = self._create_client()
        product_id = self._create_finished_product(stock_qty=200, sale_price=100, avg_cost=60)
        self._login()

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "10",
                "unit": "kg",
                "unit_price": "100",
                "sale_date": date.today().isoformat(),
                "notes": "Vente credit",
            },
            preflight_path="/sales",
        )
        sale = self._fetchone("SELECT id FROM sales WHERE client_id = ? ORDER BY id DESC", (client_id,))
        self.assertIsNotNone(sale)

        self._post_form(
            "/payments",
            {
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "400",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement initial",
            },
            preflight_path="/payments",
        )
        payment = self._fetchone("SELECT id FROM payments WHERE client_id = ? ORDER BY id DESC", (client_id,))
        self.assertIsNotNone(payment)

        invalid_edit_response = self._post_form(
            f"/payments/{int(payment['id'])}/edit",
            {
                "client_id": "999999",
                "sale_link": "",
                "amount": "250",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement invalide",
            },
            preflight_path=f"/payments/{int(payment['id'])}/edit",
        )

        self.assertEqual(invalid_edit_response.status_code, 200)
        payment_count = self._scalar("SELECT COUNT(*) FROM payments WHERE client_id = ?", (client_id,))
        original_payment = self._fetchone("SELECT id, amount FROM payments WHERE id = ?", (int(payment["id"]),))
        updated_sale = self._fetchone("SELECT amount_paid, balance_due FROM sales WHERE id = ?", (int(sale["id"]),))
        self.assertEqual(int(payment_count), 1)
        self.assertIsNotNone(original_payment)
        self.assertAlmostEqual(float(original_payment["amount"]), 400.0)
        self.assertAlmostEqual(float(updated_sale["amount_paid"]), 400.0)
        self.assertAlmostEqual(float(updated_sale["balance_due"]), 600.0)

    def test_api_edit_payment_returns_the_recreated_payment_row(self) -> None:
        client_id = self._create_client("Client API Paiement")
        product_id = self._create_finished_product(name="Produit API Paiement", stock_qty=100, sale_price=100, avg_cost=60)
        auth = self._api_login("admin", TEST_ADMIN_PASSWORD)
        headers = {"Authorization": f"Bearer {auth['access_token']}"}

        sale_response = self.client.post(
            "/api/v1/sales",
            headers=headers,
            json={
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "4",
                "unit": "kg",
                "unit_price": "100",
                "sale_date": date.today().isoformat(),
                "notes": "Vente API paiement",
            },
        )
        payment_response = self.client.post(
            "/api/v1/payments",
            headers=headers,
            json={
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "300",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement API initial",
            },
        )

        self.assertEqual(sale_response.status_code, 201)
        self.assertEqual(payment_response.status_code, 201)

        original_payment_id = int(payment_response.get_json()["data"]["payment"]["id"])
        put_response = self.client.put(
            f"/api/v1/payments/{original_payment_id}",
            headers=headers,
            json={
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "250",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement API modifie",
            },
        )

        self.assertEqual(put_response.status_code, 200)
        payload = put_response.get_json()["data"]
        latest_payment = self._fetchone("SELECT id, amount FROM payments ORDER BY id DESC LIMIT 1", ())
        updated_sale = self._fetchone("SELECT amount_paid, balance_due FROM sales ORDER BY id DESC LIMIT 1", ())

        self.assertIsNotNone(latest_payment)
        self.assertIsNotNone(updated_sale)
        self.assertNotEqual(int(payload["id"]), original_payment_id)
        self.assertEqual(int(payload["id"]), int(latest_payment["id"]))
        self.assertIsNone(self._fetchone("SELECT id FROM payments WHERE id = ?", (original_payment_id,)))
        self.assertAlmostEqual(float(payload["amount"]), 250.0)
        self.assertAlmostEqual(float(latest_payment["amount"]), 250.0)
        self.assertAlmostEqual(float(updated_sale["amount_paid"]), 250.0)
        self.assertAlmostEqual(float(updated_sale["balance_due"]), 150.0)
