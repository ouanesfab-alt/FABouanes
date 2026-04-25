from tests.business_flow_case import *  # noqa: F401,F403


class SalesBusinessFlowTests(BusinessFlowTestCase):
    def test_special_autre_item_can_be_purchased_and_sold_by_unite(self) -> None:
        supplier_id = self._create_supplier("Fournisseur AUTRE")
        client_id = self._create_client("Client AUTRE")
        other_item = self._fetchone("SELECT id, unit, stock_qty FROM raw_materials WHERE name = ?", ("AUTRE",))
        self.assertIsNotNone(other_item)
        self.assertEqual(str(other_item["unit"]), "unite")
        self._login()

        purchase_response = self._post_form(
            "/purchases",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(other_item["id"]),
                "quantity": "10",
                "unit": "unite",
                "unit_price": "120",
                "custom_item_name": "Bidon 5L",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat AUTRE",
            },
            preflight_path="/purchases",
        )
        sale_response = self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"raw:{int(other_item['id'])}",
                "quantity": "3",
                "unit": "unite",
                "unit_price": "180",
                "custom_item_name": "Piece detachee",
                "sale_date": date.today().isoformat(),
                "notes": "Vente AUTRE",
            },
            preflight_path="/sales",
        )

        purchase = self._fetchone("SELECT id, quantity, unit, unit_price, custom_item_name FROM purchases WHERE raw_material_id = ? ORDER BY id DESC LIMIT 1", (int(other_item["id"]),))
        sale = self._fetchone("SELECT id, quantity, unit, unit_price, custom_item_name FROM raw_sales WHERE raw_material_id = ? ORDER BY id DESC LIMIT 1", (int(other_item["id"]),))
        material = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (int(other_item["id"]),))

        self.assertEqual(purchase_response.status_code, 200)
        self.assertEqual(sale_response.status_code, 200)
        self.assertIsNotNone(purchase)
        self.assertIsNotNone(sale)
        self.assertIsNotNone(material)
        self.assertAlmostEqual(float(purchase["quantity"]), 10.0)
        self.assertEqual(str(purchase["unit"]), "unite")
        self.assertAlmostEqual(float(purchase["unit_price"]), 120.0)
        self.assertEqual(str(purchase["custom_item_name"]), "Bidon 5L")
        self.assertAlmostEqual(float(sale["quantity"]), 3.0)
        self.assertEqual(str(sale["unit"]), "unite")
        self.assertAlmostEqual(float(sale["unit_price"]), 180.0)
        self.assertEqual(str(sale["custom_item_name"]), "Piece detachee")
        self.assertAlmostEqual(float(material["stock_qty"]), 7.0)

        purchase_print = html.unescape(self.client.get(f"/print/purchase/{int(purchase['id'])}").get_data(as_text=True))
        sale_print = html.unescape(self.client.get(f"/print/sale_raw/{int(sale['id'])}").get_data(as_text=True))
        transactions_body = html.unescape(self.client.get("/transactions").get_data(as_text=True))

        self.assertIn("Bidon 5L", purchase_print)
        self.assertIn("Piece detachee", sale_print)
        self.assertIn("Bidon 5L", transactions_body)
        self.assertIn("Piece detachee", transactions_body)

    def test_autre_requires_a_custom_product_name(self) -> None:
        other_item = self._fetchone("SELECT id FROM raw_materials WHERE name = ?", ("AUTRE",))
        self.assertIsNotNone(other_item)
        self._login()

        purchase_response = self._post_form(
            "/purchases",
            {
                "raw_material_id": str(other_item["id"]),
                "quantity": "2",
                "unit": "unite",
                "unit_price": "100",
                "custom_item_name": "",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat invalide",
            },
            preflight_path="/purchases",
        )
        sale_response = self._post_form(
            "/sales",
            {
                "item_key": f"raw:{int(other_item['id'])}",
                "quantity": "1",
                "unit": "unite",
                "unit_price": "150",
                "custom_item_name": "",
                "sale_date": date.today().isoformat(),
                "notes": "Vente invalide",
            },
            preflight_path="/sales",
        )

        self.assertEqual(purchase_response.status_code, 200)
        self.assertEqual(sale_response.status_code, 200)
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM purchases WHERE raw_material_id = ?", (int(other_item["id"]),))), 0)
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM raw_sales WHERE raw_material_id = ?", (int(other_item["id"]),))), 0)

    def test_multi_line_sale_creates_one_document_and_prints_all_lines(self) -> None:
        client_id = self._create_client("Client Facture Multiple")
        product_id = self._create_finished_product(name="Aliment BV", stock_qty=1000, sale_price=70, avg_cost=40)
        raw_id = self._create_raw_material(name="Soja", stock_qty=120, avg_cost=55, sale_price=65)
        self._login()

        response = self._post_form(
            "/sales/new",
            {
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Facture multi-lignes",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_id}"],
                "quantity[]": ["10", "5"],
                "unit[]": ["sac", "kg"],
                "unit_price[]": ["3000", "120"],
            },
            preflight_path="/sales/new",
        )

        self.assertEqual(response.status_code, 200)
        document = self._fetchone("SELECT id, total, amount_paid, balance_due FROM sale_documents ORDER BY id DESC LIMIT 1")
        finished_sale = self._fetchone("SELECT id, document_id FROM sales ORDER BY id DESC LIMIT 1")
        raw_sale = self._fetchone("SELECT id, document_id FROM raw_sales ORDER BY id DESC LIMIT 1")
        product = self._fetchone("SELECT stock_qty FROM finished_products WHERE id = ?", (product_id,))
        raw = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_id,))

        self.assertIsNotNone(document)
        self.assertIsNotNone(finished_sale)
        self.assertIsNotNone(raw_sale)
        self.assertEqual(int(finished_sale["document_id"]), int(document["id"]))
        self.assertEqual(int(raw_sale["document_id"]), int(document["id"]))
        self.assertAlmostEqual(float(document["total"]), 30600.0)
        self.assertAlmostEqual(float(document["amount_paid"]), 0.0)
        self.assertAlmostEqual(float(document["balance_due"]), 30600.0)
        self.assertAlmostEqual(float(product["stock_qty"]), 500.0)
        self.assertAlmostEqual(float(raw["stock_qty"]), 115.0)

        print_response = self.client.get(f"/print/sale_document/{int(document['id'])}")
        line_print_response = self.client.get(f"/print/sale_finished/{int(finished_sale['id'])}")
        print_body = html.unescape(print_response.get_data(as_text=True))
        line_print_body = html.unescape(line_print_response.get_data(as_text=True))

        self.assertEqual(print_response.status_code, 200)
        self.assertEqual(line_print_response.status_code, 200)
        self.assertIn("Aliment BV", print_body)
        self.assertIn("Soja", print_body)
        self.assertIn("Facture", print_body)
        self.assertIn("Vente multi-produits", print_body)
        self.assertIn("Aliment BV", line_print_body)
        self.assertIn("Soja", line_print_body)

    def test_multi_line_sale_edit_updates_existing_document_and_preserves_document_id(self) -> None:
        client_id = self._create_client("Client Facture Edition")
        product_id = self._create_finished_product(name="Aliment Edition", stock_qty=1000, sale_price=70, avg_cost=40)
        raw_a = self._create_raw_material(name="Soja Edition", stock_qty=50, avg_cost=55, sale_price=65)
        raw_b = self._create_raw_material(name="Mais Edition", stock_qty=80, avg_cost=35, sale_price=45)
        self._login()

        self._post_form(
            "/sales/new",
            {
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Facture a modifier",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_a}"],
                "quantity[]": ["10", "5"],
                "unit[]": ["sac", "kg"],
                "unit_price[]": ["3000", "120"],
            },
            preflight_path="/sales/new",
        )
        document = self._fetchone("SELECT id FROM sale_documents ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(document)
        document_id = int(document["id"])

        response = self._post_form(
            f"/sales/document/{document_id}/edit",
            {
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Facture multi-lignes modifiee",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_a}", f"raw:{raw_b}"],
                "quantity[]": ["5", "2", "4"],
                "unit[]": ["sac", "kg", "kg"],
                "unit_price[]": ["2500", "120", "200"],
            },
            preflight_path=f"/sales/document/{document_id}/edit",
        )

        updated_document = self._fetchone("SELECT id, total, balance_due, notes FROM sale_documents WHERE id = ?", (document_id,))
        product = self._fetchone("SELECT stock_qty FROM finished_products WHERE id = ?", (product_id,))
        raw_a_row = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_a,))
        raw_b_row = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_b,))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(updated_document)
        self.assertEqual(int(updated_document["id"]), document_id)
        self.assertAlmostEqual(float(updated_document["total"]), 13540.0)
        self.assertAlmostEqual(float(updated_document["balance_due"]), 13540.0)
        self.assertEqual(str(updated_document["notes"]), "Facture multi-lignes modifiee")
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM sales WHERE document_id = ?", (document_id,))), 1)
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM raw_sales WHERE document_id = ?", (document_id,))), 2)
        self.assertAlmostEqual(float(product["stock_qty"]), 750.0)
        self.assertAlmostEqual(float(raw_a_row["stock_qty"]), 48.0)
        self.assertAlmostEqual(float(raw_b_row["stock_qty"]), 76.0)

        print_response = self.client.get(f"/print/sale_document/{document_id}")
        print_body = html.unescape(print_response.get_data(as_text=True))
        self.assertEqual(print_response.status_code, 200)
        self.assertIn("Aliment Edition", print_body)
        self.assertIn("Soja Edition", print_body)
        self.assertIn("Mais Edition", print_body)
        self.assertIn("Vente multi-produits", print_body)

    def test_simple_sale_edit_can_promote_to_multi_line_document(self) -> None:
        client_id = self._create_client("Client Promotion Vente")
        product_id = self._create_finished_product(name="Produit Promotion", stock_qty=500, sale_price=100, avg_cost=55)
        raw_id = self._create_raw_material(name="Soja Promotion", stock_qty=30, avg_cost=40, sale_price=60)
        self._login()

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "2",
                "unit": "kg",
                "unit_price": "100",
                "sale_date": date.today().isoformat(),
                "notes": "Vente simple",
            },
            preflight_path="/sales",
        )
        sale = self._fetchone("SELECT id FROM sales ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(sale)

        response = self._post_form(
            f"/sales/finished/{int(sale['id'])}/edit",
            {
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Vente promue",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_id}"],
                "quantity[]": ["1", "3"],
                "unit[]": ["kg", "kg"],
                "unit_price[]": ["100", "60"],
            },
            preflight_path=f"/sales/finished/{int(sale['id'])}/edit",
        )

        document = self._fetchone("SELECT id, total FROM sale_documents ORDER BY id DESC LIMIT 1")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(document)
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM sales WHERE document_id = ?", (int(document['id']),))), 1)
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM raw_sales WHERE document_id = ?", (int(document['id']),))), 1)
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM sales WHERE id = ?", (int(sale["id"]),))), 0)
        self.assertAlmostEqual(float(document["total"]), 280.0)

    def test_document_edit_routes_redirect_from_line_rows(self) -> None:
        client_id = self._create_client("Client Redirection Doc")
        supplier_id = self._create_supplier("Fournisseur Redirection Doc")
        product_id = self._create_finished_product(name="Produit Redirection", stock_qty=500, sale_price=90, avg_cost=55)
        raw_sale_id = self._create_raw_material(name="Soja Redirection", stock_qty=40, avg_cost=30, sale_price=50)
        raw_purchase_id = self._create_raw_material(name="Mais Redirection", stock_qty=20, avg_cost=15, sale_price=25)
        self._login()

        self._post_form(
            "/sales/new",
            {
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Doc vente redirection",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_sale_id}"],
                "quantity[]": ["1", "2"],
                "unit[]": ["kg", "kg"],
                "unit_price[]": ["90", "50"],
            },
            preflight_path="/sales/new",
        )
        sale_document = self._fetchone("SELECT id FROM sale_documents ORDER BY id DESC LIMIT 1")
        sale_line = self._fetchone("SELECT id FROM sales ORDER BY id DESC LIMIT 1")

        self._post_form(
            "/purchases/new",
            {
                "supplier_id": str(supplier_id),
                "purchase_date": date.today().isoformat(),
                "notes": "Doc achat redirection",
                "raw_material_id[]": [str(raw_sale_id), str(raw_purchase_id)],
                "quantity[]": ["3", "4"],
                "unit[]": ["kg", "kg"],
                "unit_price[]": ["40", "30"],
            },
            preflight_path="/purchases/new",
        )
        purchase_document = self._fetchone("SELECT id FROM purchase_documents ORDER BY id DESC LIMIT 1")
        purchase_line = self._fetchone("SELECT id FROM purchases ORDER BY id DESC LIMIT 1")

        sale_response = self.client.get(f"/sales/finished/{int(sale_line['id'])}/edit", follow_redirects=False)
        purchase_response = self.client.get(f"/purchases/{int(purchase_line['id'])}/edit", follow_redirects=False)

        self.assertEqual(sale_response.status_code, 302)
        self.assertIn(f"/sales/document/{int(sale_document['id'])}/edit", str(sale_response.headers.get("Location")))
        self.assertEqual(purchase_response.status_code, 302)
        self.assertIn(f"/purchases/document/{int(purchase_document['id'])}/edit", str(purchase_response.headers.get("Location")))

    def test_mobile_api_sale_document_endpoints_edit_and_block_paid_documents(self) -> None:
        self._create_user("mobile_doc_manager", TEST_MANAGER_PASSWORD, role="manager")
        client_id = self._create_client("Client API Facture")
        product_id = self._create_finished_product(name="Produit API Facture", stock_qty=200, sale_price=100, avg_cost=60)
        raw_a = self._create_raw_material(name="Soja API Facture", stock_qty=30, avg_cost=40, sale_price=50)
        raw_b = self._create_raw_material(name="Mais API Facture", stock_qty=40, avg_cost=30, sale_price=45)
        auth = self._api_login("mobile_doc_manager", TEST_MANAGER_PASSWORD)
        headers = {"Authorization": f"Bearer {auth['access_token']}"}

        create_response = self.client.post(
            "/api/v1/sales",
            headers=headers,
            json={
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Facture API multi-lignes",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_a}"],
                "quantity[]": ["2", "3"],
                "unit[]": ["kg", "kg"],
                "unit_price[]": ["100", "50"],
            },
        )
        document = self._fetchone("SELECT id FROM sale_documents ORDER BY id DESC LIMIT 1")
        line = self._fetchone("SELECT id FROM sales ORDER BY id DESC LIMIT 1")

        get_document_response = self.client.get(f"/api/v1/sale-documents/{int(document['id'])}", headers=headers)
        line_put_response = self.client.put(
            f"/api/v1/sales/finished/{int(line['id'])}",
            headers=headers,
            json={
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Tentative ligne",
                "item_key[]": [f"finished:{product_id}"],
                "quantity[]": ["1"],
                "unit[]": ["kg"],
                "unit_price[]": ["100"],
            },
        )
        update_document_response = self.client.put(
            f"/api/v1/sale-documents/{int(document['id'])}",
            headers=headers,
            json={
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Facture API modifiee",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_a}", f"raw:{raw_b}"],
                "quantity[]": ["1", "2", "4"],
                "unit[]": ["kg", "kg", "kg"],
                "unit_price[]": ["100", "55", "60"],
            },
        )
        payment_response = self.client.post(
            "/api/v1/payments",
            headers=headers,
            json={
                "client_id": str(client_id),
                "amount": "50",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement facture API",
                "sale_link": "",
            },
        )
        blocked_update_response = self.client.put(
            f"/api/v1/sale-documents/{int(document['id'])}",
            headers=headers,
            json={
                "client_id": str(client_id),
                "sale_date": date.today().isoformat(),
                "notes": "Facture API bloquee",
                "item_key[]": [f"finished:{product_id}", f"raw:{raw_a}"],
                "quantity[]": ["1", "1"],
                "unit[]": ["kg", "kg"],
                "unit_price[]": ["100", "55"],
            },
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(get_document_response.status_code, 200)
        self.assertEqual(line_put_response.status_code, 409)
        self.assertEqual(update_document_response.status_code, 200)
        self.assertEqual(payment_response.status_code, 201)
        self.assertEqual(blocked_update_response.status_code, 409)

        get_payload = get_document_response.get_json()["data"]
        line_error = line_put_response.get_json()["error"]
        update_payload = update_document_response.get_json()["data"]
        blocked_error = blocked_update_response.get_json()["error"]

        self.assertEqual(int(get_payload["document"]["id"]), int(document["id"]))
        self.assertEqual(len(get_payload["lines"]), 2)
        self.assertEqual(line_error["code"], "document_edit_required")
        self.assertEqual(int(line_error["details"]["document_id"]), int(document["id"]))
        self.assertEqual(int(update_payload["document"]["id"]), int(document["id"]))
        self.assertEqual(len(update_payload["lines"]), 3)
        self.assertEqual(blocked_error["code"], "document_has_payments")

    def test_credit_sale_then_payment_updates_balance_and_stock(self) -> None:
        client_id = self._create_client()
        product_id = self._create_finished_product(stock_qty=200, sale_price=100, avg_cost=60)
        self._login()

        sale_response = self._post_form(
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

        self.assertEqual(sale_response.status_code, 200)
        sale = self._fetchone(
            "SELECT id, total, amount_paid, balance_due FROM sales WHERE client_id = ? ORDER BY id DESC",
            (client_id,),
        )
        product_after_sale = self._fetchone("SELECT stock_qty FROM finished_products WHERE id = ?", (product_id,))
        self.assertIsNotNone(sale)
        self.assertAlmostEqual(float(sale["total"]), 1000.0)
        self.assertAlmostEqual(float(sale["amount_paid"]), 0.0)
        self.assertAlmostEqual(float(sale["balance_due"]), 1000.0)
        self.assertAlmostEqual(float(product_after_sale["stock_qty"]), 190.0)

        payment_response = self._post_form(
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

        self.assertEqual(payment_response.status_code, 200)
        updated_sale = self._fetchone("SELECT amount_paid, balance_due FROM sales WHERE id = ?", (int(sale["id"]),))
        payment = self._fetchone(
            "SELECT amount, payment_type, allocation_meta FROM payments WHERE client_id = ? ORDER BY id DESC",
            (client_id,),
        )
        self.assertIsNotNone(updated_sale)
        self.assertIsNotNone(payment)
        self.assertAlmostEqual(float(updated_sale["amount_paid"]), 400.0)
        self.assertAlmostEqual(float(updated_sale["balance_due"]), 600.0)
        self.assertAlmostEqual(float(payment["amount"]), 400.0)
        self.assertEqual(str(payment["payment_type"]), "versement")
        self.assertIn('"kind": "finished"', str(payment["allocation_meta"]))

    def test_deleting_finished_sale_in_sacks_restores_stock(self) -> None:
        product_id = self._create_finished_product(stock_qty=100, sale_price=3500, avg_cost=60)
        self._login()

        sale_response = self._post_form(
            "/sales",
            {
                "item_key": f"finished:{product_id}",
                "quantity": "1",
                "unit": "sac",
                "unit_price": "3500",
                "sale_date": date.today().isoformat(),
                "notes": "Vente comptoir",
            },
            preflight_path="/sales",
        )

        self.assertEqual(sale_response.status_code, 200)
        sale = self._fetchone("SELECT id FROM sales WHERE finished_product_id = ? ORDER BY id DESC", (product_id,))
        product_after_sale = self._fetchone("SELECT stock_qty FROM finished_products WHERE id = ?", (product_id,))
        self.assertIsNotNone(sale)
        self.assertAlmostEqual(float(product_after_sale["stock_qty"]), 50.0)

        delete_response = self._post_form(
            f"/sales/finished/{int(sale['id'])}/delete",
            {},
            preflight_path="/sales",
        )

        self.assertEqual(delete_response.status_code, 200)
        product_after_delete = self._fetchone("SELECT stock_qty FROM finished_products WHERE id = ?", (product_id,))
        deleted_sale = self._fetchone("SELECT id FROM sales WHERE id = ?", (int(sale["id"]),))
        self.assertIsNotNone(product_after_delete)
        self.assertAlmostEqual(float(product_after_delete["stock_qty"]), 100.0)
        self.assertIsNone(deleted_sale)

    def test_edit_sale_replaces_row_and_restores_correct_stock(self) -> None:
        product_id = self._create_finished_product(stock_qty=200, sale_price=120, avg_cost=60)
        self._login()

        self._post_form(
            "/sales",
            {
                "item_key": f"finished:{product_id}",
                "quantity": "10",
                "unit": "kg",
                "unit_price": "120",
                "sale_date": date.today().isoformat(),
                "notes": "Vente initiale",
            },
            preflight_path="/sales",
        )
        sale = self._fetchone("SELECT id FROM sales WHERE finished_product_id = ? ORDER BY id DESC", (product_id,))
        self.assertIsNotNone(sale)

        edit_response = self._post_form(
            f"/sales/finished/{int(sale['id'])}/edit",
            {
                "client_id": "",
                "item_key": f"finished:{product_id}",
                "quantity": "5",
                "unit": "kg",
                "unit_price": "120",
                "sale_date": date.today().isoformat(),
                "notes": "Vente modifiee",
            },
            preflight_path=f"/sales/finished/{int(sale['id'])}/edit",
        )

        self.assertEqual(edit_response.status_code, 200)
        sale_count = self._scalar("SELECT COUNT(*) FROM sales WHERE finished_product_id = ?", (product_id,))
        current_sale = self._fetchone(
            "SELECT quantity, total, amount_paid, balance_due FROM sales WHERE finished_product_id = ? ORDER BY id DESC",
            (product_id,),
        )
        product = self._fetchone("SELECT stock_qty FROM finished_products WHERE id = ?", (product_id,))
        self.assertEqual(int(sale_count), 1)
        self.assertAlmostEqual(float(current_sale["quantity"]), 5.0)
        self.assertAlmostEqual(float(current_sale["total"]), 600.0)
        self.assertAlmostEqual(float(current_sale["amount_paid"]), 600.0)
        self.assertAlmostEqual(float(current_sale["balance_due"]), 0.0)
        self.assertAlmostEqual(float(product["stock_qty"]), 195.0)

    def test_edit_sale_rollback_keeps_original_row_when_stock_is_insufficient(self) -> None:
        product_id = self._create_finished_product(stock_qty=20, sale_price=120, avg_cost=60)
        self._login()

        self._post_form(
            "/sales",
            {
                "item_key": f"finished:{product_id}",
                "quantity": "10",
                "unit": "kg",
                "unit_price": "120",
                "sale_date": date.today().isoformat(),
                "notes": "Vente initiale",
            },
            preflight_path="/sales",
        )
        sale = self._fetchone(
            "SELECT id, quantity, total FROM sales WHERE finished_product_id = ? ORDER BY id DESC",
            (product_id,),
        )
        self.assertIsNotNone(sale)

        invalid_response = self._post_form(
            f"/sales/finished/{int(sale['id'])}/edit",
            {
                "client_id": "",
                "item_key": f"finished:{product_id}",
                "quantity": "25",
                "unit": "kg",
                "unit_price": "120",
                "sale_date": date.today().isoformat(),
                "notes": "Edition invalide",
            },
            preflight_path=f"/sales/finished/{int(sale['id'])}/edit",
        )

        self.assertEqual(invalid_response.status_code, 200)
        sale_count = self._scalar("SELECT COUNT(*) FROM sales WHERE finished_product_id = ?", (product_id,))
        current_sale = self._fetchone(
            "SELECT id, quantity, total FROM sales WHERE finished_product_id = ? ORDER BY id DESC",
            (product_id,),
        )
        product = self._fetchone("SELECT stock_qty FROM finished_products WHERE id = ?", (product_id,))
        self.assertEqual(int(sale_count), 1)
        self.assertEqual(int(current_sale["id"]), int(sale["id"]))
        self.assertAlmostEqual(float(current_sale["quantity"]), 10.0)
        self.assertAlmostEqual(float(current_sale["total"]), 1200.0)
        self.assertAlmostEqual(float(product["stock_qty"]), 10.0)
