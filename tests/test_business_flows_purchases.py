from tests.business_flow_case import *  # noqa: F401,F403


class PurchasesBusinessFlowTests(BusinessFlowTestCase):
    def test_multi_line_purchase_creates_one_document_and_prints_all_lines(self) -> None:
        supplier_id = self._create_supplier("Fournisseur Bon Multiple")
        raw_a = self._create_raw_material(name="Mais", stock_qty=10, avg_cost=40, sale_price=50)
        raw_b = self._create_raw_material(name="Son", stock_qty=20, avg_cost=30, sale_price=40)
        self._login()

        response = self._post_form(
            "/purchases/new",
            {
                "supplier_id": str(supplier_id),
                "purchase_date": date.today().isoformat(),
                "notes": "Bon d'achat multi-lignes",
                "raw_material_id[]": [str(raw_a), str(raw_b)],
                "quantity[]": ["2", "10"],
                "unit[]": ["sac", "kg"],
                "unit_price[]": ["2500", "60"],
            },
            preflight_path="/purchases/new",
        )

        self.assertEqual(response.status_code, 200)
        document = self._fetchone("SELECT id, total FROM purchase_documents ORDER BY id DESC LIMIT 1")
        first_purchase = self._fetchone("SELECT id, document_id, unit FROM purchases WHERE raw_material_id = ? ORDER BY id DESC LIMIT 1", (raw_a,))
        second_purchase = self._fetchone("SELECT id, document_id, unit FROM purchases WHERE raw_material_id = ? ORDER BY id DESC LIMIT 1", (raw_b,))
        material_a = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_a,))
        material_b = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_b,))

        self.assertIsNotNone(document)
        self.assertIsNotNone(first_purchase)
        self.assertIsNotNone(second_purchase)
        self.assertEqual(int(first_purchase["document_id"]), int(document["id"]))
        self.assertEqual(int(second_purchase["document_id"]), int(document["id"]))
        self.assertEqual(str(first_purchase["unit"]), "sac")
        self.assertEqual(str(second_purchase["unit"]), "kg")
        self.assertAlmostEqual(float(document["total"]), 5600.0)
        self.assertAlmostEqual(float(material_a["stock_qty"]), 110.0)
        self.assertAlmostEqual(float(material_b["stock_qty"]), 30.0)

        print_response = self.client.get(f"/print/purchase_document/{int(document['id'])}")
        line_print_response = self.client.get(f"/print/purchase/{int(first_purchase['id'])}")
        print_body = html.unescape(print_response.get_data(as_text=True))
        line_print_body = html.unescape(line_print_response.get_data(as_text=True))

        self.assertEqual(print_response.status_code, 200)
        self.assertEqual(line_print_response.status_code, 200)
        self.assertIn("Mais", print_body)
        self.assertIn("Son", print_body)
        self.assertIn("Bon d'achat", print_body)
        self.assertIn("Achat multi-produits", print_body)
        self.assertIn("Mais", line_print_body)
        self.assertIn("Son", line_print_body)

    def test_multi_line_purchase_edit_updates_existing_document_and_preserves_document_id(self) -> None:
        supplier_id = self._create_supplier("Fournisseur Edition Achat")
        raw_a = self._create_raw_material(name="Mais Achat Edition", stock_qty=10, avg_cost=40, sale_price=50)
        raw_b = self._create_raw_material(name="Son Achat Edition", stock_qty=20, avg_cost=30, sale_price=40)
        raw_c = self._create_raw_material(name="Sel Achat Edition", stock_qty=30, avg_cost=10, sale_price=20)
        self._login()

        self._post_form(
            "/purchases/new",
            {
                "supplier_id": str(supplier_id),
                "purchase_date": date.today().isoformat(),
                "notes": "Bon a modifier",
                "raw_material_id[]": [str(raw_a), str(raw_b)],
                "quantity[]": ["2", "10"],
                "unit[]": ["sac", "kg"],
                "unit_price[]": ["2500", "60"],
            },
            preflight_path="/purchases/new",
        )
        document = self._fetchone("SELECT id FROM purchase_documents ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(document)
        document_id = int(document["id"])

        response = self._post_form(
            f"/purchases/document/{document_id}/edit",
            {
                "supplier_id": str(supplier_id),
                "purchase_date": date.today().isoformat(),
                "notes": "Bon multi-lignes modifie",
                "raw_material_id[]": [str(raw_a), str(raw_c)],
                "quantity[]": ["1", "5"],
                "unit[]": ["sac", "kg"],
                "unit_price[]": ["2400", "70"],
            },
            preflight_path=f"/purchases/document/{document_id}/edit",
        )

        updated_document = self._fetchone("SELECT id, total, notes FROM purchase_documents WHERE id = ?", (document_id,))
        raw_a_row = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_a,))
        raw_b_row = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_b,))
        raw_c_row = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_c,))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(updated_document)
        self.assertEqual(int(updated_document["id"]), document_id)
        self.assertAlmostEqual(float(updated_document["total"]), 2750.0)
        self.assertEqual(str(updated_document["notes"]), "Bon multi-lignes modifie")
        self.assertEqual(int(self._scalar("SELECT COUNT(*) FROM purchases WHERE document_id = ?", (document_id,))), 2)
        self.assertAlmostEqual(float(raw_a_row["stock_qty"]), 60.0)
        self.assertAlmostEqual(float(raw_b_row["stock_qty"]), 20.0)
        self.assertAlmostEqual(float(raw_c_row["stock_qty"]), 35.0)

    def test_mobile_api_purchase_document_endpoints_allow_full_document_edit(self) -> None:
        self._create_user("mobile_doc_buyer", TEST_MANAGER_PASSWORD, role="manager")
        supplier_id = self._create_supplier("Fournisseur API Bon")
        raw_a = self._create_raw_material(name="Mais API Bon", stock_qty=10, avg_cost=20, sale_price=30)
        raw_b = self._create_raw_material(name="Son API Bon", stock_qty=15, avg_cost=25, sale_price=35)
        raw_c = self._create_raw_material(name="Sel API Bon", stock_qty=8, avg_cost=10, sale_price=15)
        auth = self._api_login("mobile_doc_buyer", TEST_MANAGER_PASSWORD)
        headers = {"Authorization": f"Bearer {auth['access_token']}"}

        create_response = self.client.post(
            "/api/v1/purchases",
            headers=headers,
            json={
                "supplier_id": str(supplier_id),
                "purchase_date": date.today().isoformat(),
                "notes": "Bon API multi-lignes",
                "raw_material_id[]": [str(raw_a), str(raw_b)],
                "quantity[]": ["2", "4"],
                "unit[]": ["kg", "kg"],
                "unit_price[]": ["20", "25"],
            },
        )
        document = self._fetchone("SELECT id FROM purchase_documents ORDER BY id DESC LIMIT 1")
        line = self._fetchone("SELECT id FROM purchases ORDER BY id DESC LIMIT 1")

        get_document_response = self.client.get(f"/api/v1/purchase-documents/{int(document['id'])}", headers=headers)
        line_put_response = self.client.put(
            f"/api/v1/purchases/{int(line['id'])}",
            headers=headers,
            json={
                "supplier_id": str(supplier_id),
                "purchase_date": date.today().isoformat(),
                "notes": "Tentative ligne achat",
                "raw_material_id[]": [str(raw_a)],
                "quantity[]": ["1"],
                "unit[]": ["kg"],
                "unit_price[]": ["20"],
            },
        )
        update_document_response = self.client.put(
            f"/api/v1/purchase-documents/{int(document['id'])}",
            headers=headers,
            json={
                "supplier_id": str(supplier_id),
                "purchase_date": date.today().isoformat(),
                "notes": "Bon API modifie",
                "raw_material_id[]": [str(raw_a), str(raw_c)],
                "quantity[]": ["1", "3"],
                "unit[]": ["kg", "kg"],
                "unit_price[]": ["22", "12"],
            },
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(get_document_response.status_code, 200)
        self.assertEqual(line_put_response.status_code, 409)
        self.assertEqual(update_document_response.status_code, 200)

        get_payload = get_document_response.get_json()["data"]
        line_error = line_put_response.get_json()["error"]
        update_payload = update_document_response.get_json()["data"]

        self.assertEqual(int(get_payload["document"]["id"]), int(document["id"]))
        self.assertEqual(len(get_payload["lines"]), 2)
        self.assertEqual(line_error["code"], "document_edit_required")
        self.assertEqual(int(line_error["details"]["document_id"]), int(document["id"]))
        self.assertEqual(int(update_payload["document"]["id"]), int(document["id"]))
        self.assertEqual(len(update_payload["lines"]), 2)

    def test_purchase_route_converts_sacks_to_stock_in_kg(self) -> None:
        supplier_id = self._create_supplier()
        raw_id = self._create_raw_material()
        self._login()

        response = self._post_form(
            "/purchases",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "2",
                "unit": "sac",
                "unit_price": "2500",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat test",
            },
            preflight_path="/purchases",
        )

        self.assertEqual(response.status_code, 200)
        material = self._fetchone("SELECT stock_qty, avg_cost, sale_price FROM raw_materials WHERE id = ?", (raw_id,))
        purchase = self._fetchone("SELECT quantity, unit_price, total FROM purchases WHERE raw_material_id = ?", (raw_id,))
        self.assertIsNotNone(material)
        self.assertIsNotNone(purchase)
        self.assertAlmostEqual(float(material["stock_qty"]), 100.0)
        self.assertAlmostEqual(float(material["avg_cost"]), 50.0)
        self.assertAlmostEqual(float(material["sale_price"]), 2500.0)
        self.assertAlmostEqual(float(purchase["quantity"]), 100.0)
        self.assertAlmostEqual(float(purchase["unit_price"]), 50.0)
        self.assertAlmostEqual(float(purchase["total"]), 5000.0)

    def test_edit_purchase_replaces_previous_quantity_and_stock(self) -> None:
        supplier_id = self._create_supplier()
        raw_id = self._create_raw_material(stock_qty=0, avg_cost=0, sale_price=0)
        self._login()

        self._post_form(
            "/purchases",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "2",
                "unit": "sac",
                "unit_price": "2500",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat initial",
            },
            preflight_path="/purchases",
        )
        purchase = self._fetchone("SELECT id FROM purchases WHERE raw_material_id = ? ORDER BY id DESC", (raw_id,))
        self.assertIsNotNone(purchase)

        edit_response = self._post_form(
            f"/purchases/{int(purchase['id'])}/edit",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "1",
                "unit": "sac",
                "unit_price": "3000",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat modifie",
            },
            preflight_path=f"/purchases/{int(purchase['id'])}/edit",
        )

        self.assertEqual(edit_response.status_code, 200)
        purchase_count = self._scalar("SELECT COUNT(*) FROM purchases WHERE raw_material_id = ?", (raw_id,))
        edited_purchase = self._fetchone(
            "SELECT quantity, unit_price, total FROM purchases WHERE raw_material_id = ? ORDER BY id DESC",
            (raw_id,),
        )
        material = self._fetchone("SELECT stock_qty, avg_cost FROM raw_materials WHERE id = ?", (raw_id,))
        self.assertEqual(int(purchase_count), 1)
        self.assertAlmostEqual(float(edited_purchase["quantity"]), 50.0)
        self.assertAlmostEqual(float(edited_purchase["unit_price"]), 60.0)
        self.assertAlmostEqual(float(edited_purchase["total"]), 3000.0)
        self.assertAlmostEqual(float(material["stock_qty"]), 50.0)
        self.assertAlmostEqual(float(material["avg_cost"]), 60.0)

    def test_edit_purchase_rollback_keeps_original_row_when_new_data_is_invalid(self) -> None:
        supplier_id = self._create_supplier()
        raw_id = self._create_raw_material(stock_qty=0, avg_cost=0, sale_price=0)
        self._login()

        self._post_form(
            "/purchases",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "2",
                "unit": "sac",
                "unit_price": "2500",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat initial",
            },
            preflight_path="/purchases",
        )
        purchase = self._fetchone(
            "SELECT id, quantity, unit_price, total FROM purchases WHERE raw_material_id = ? ORDER BY id DESC",
            (raw_id,),
        )
        self.assertIsNotNone(purchase)

        invalid_response = self._post_form(
            f"/purchases/{int(purchase['id'])}/edit",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "1",
                "unit": "sac",
                "unit_price": "3000",
                "purchase_date": "2999-12-31",
                "notes": "Edition invalide",
            },
            preflight_path=f"/purchases/{int(purchase['id'])}/edit",
        )

        self.assertEqual(invalid_response.status_code, 200)
        purchase_count = self._scalar("SELECT COUNT(*) FROM purchases WHERE raw_material_id = ?", (raw_id,))
        current_purchase = self._fetchone(
            "SELECT id, quantity, unit_price, total FROM purchases WHERE raw_material_id = ? ORDER BY id DESC",
            (raw_id,),
        )
        material = self._fetchone("SELECT stock_qty, avg_cost FROM raw_materials WHERE id = ?", (raw_id,))
        self.assertEqual(int(purchase_count), 1)
        self.assertEqual(int(current_purchase["id"]), int(purchase["id"]))
        self.assertAlmostEqual(float(current_purchase["quantity"]), 100.0)
        self.assertAlmostEqual(float(current_purchase["unit_price"]), 50.0)
        self.assertAlmostEqual(float(current_purchase["total"]), 5000.0)
        self.assertAlmostEqual(float(material["stock_qty"]), 100.0)
        self.assertAlmostEqual(float(material["avg_cost"]), 50.0)
