from tests.business_flow_case import *  # noqa: F401,F403


class MobileBusinessFlowTests(BusinessFlowTestCase):
    def test_mobile_api_ping_and_cors_preflight_are_available(self) -> None:
        ping_response = self.client.get(
            "/api/v1/ping",
            headers={"Origin": "http://localhost"},
        )
        options_response = self.client.open(
            "/api/v1/dashboard/summary",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization, content-type",
            },
        )

        self.assertEqual(ping_response.status_code, 200)
        self.assertEqual(ping_response.get_json()["data"]["service"], "FABOuanes")
        self.assertEqual(ping_response.headers.get("Access-Control-Allow-Origin"), "http://localhost")
        self.assertEqual(options_response.status_code, 200)
        self.assertEqual(options_response.headers.get("Access-Control-Allow-Origin"), "http://localhost")
        self.assertIn("Authorization", str(options_response.headers.get("Access-Control-Allow-Headers")))
        self.assertIn("OPTIONS", str(options_response.headers.get("Access-Control-Allow-Methods")))

    def test_mobile_api_clients_history_and_list_are_enriched(self) -> None:
        self._create_user("mobile_manager", TEST_MANAGER_PASSWORD, role="manager")
        client_id = self._create_client("Client Mobile Historique")
        product_id = self._create_finished_product(name="Produit Mobile", stock_qty=100, sale_price=100, avg_cost=60)
        auth = self._api_login("mobile_manager", TEST_MANAGER_PASSWORD)
        headers = {"Authorization": f"Bearer {auth['access_token']}", "Origin": "http://localhost"}

        sale_response = self.client.post(
            "/api/v1/sales",
            headers=headers,
            json={
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "2",
                "unit": "kg",
                "unit_price": "100",
                "sale_date": date.today().isoformat(),
                "notes": "Vente mobile",
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
                "notes": "Versement mobile",
                "sale_link": "",
            },
        )
        clients_response = self.client.get(
            "/api/v1/clients?q=Historique",
            headers=headers,
        )
        detail_response = self.client.get(
            f"/api/v1/clients/{client_id}",
            headers=headers,
        )
        history_response = self.client.get(
            f"/api/v1/clients/{client_id}/history",
            headers=headers,
        )

        self.assertEqual(sale_response.status_code, 201)
        self.assertEqual(payment_response.status_code, 201)
        self.assertEqual(clients_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(history_response.status_code, 200)

        client_row = clients_response.get_json()["data"][0]
        detail_payload = detail_response.get_json()["data"]
        history_payload = history_response.get_json()["data"]

        self.assertEqual(client_row["name"], "Client Mobile Historique")
        self.assertAlmostEqual(float(client_row["current_balance"]), 150.0)
        self.assertAlmostEqual(float(client_row["total_sales"]), 200.0)
        self.assertAlmostEqual(float(client_row["total_payments"]), 50.0)
        self.assertIn("summary", detail_payload)
        self.assertAlmostEqual(float(detail_payload["summary"]["current_balance"]), 150.0)
        self.assertEqual(history_payload["client"]["name"], "Client Mobile Historique")
        self.assertGreaterEqual(len(history_payload["history"]), 2)
        self.assertAlmostEqual(float(history_payload["current_balance"]), 150.0)

    def test_mobile_api_filters_sellable_items_and_recent_operations(self) -> None:
        self._create_user("mobile_operator", TEST_OPERATOR_PASSWORD, role="operator")
        client_id = self._create_client("Client Mobile Operations")
        supplier_id = self._create_supplier("Fournisseur Mobile")
        raw_id = self._create_raw_material(name="Matiere Mobile", stock_qty=0.5, avg_cost=20, sale_price=30)
        self._execute("UPDATE raw_materials SET alert_threshold = 2, threshold_qty = 2 WHERE id = ?", (raw_id,))
        product_id = self._create_finished_product(name="Produit Mobile Rapide", stock_qty=50, sale_price=90, avg_cost=55)
        auth = self._api_login("mobile_operator", TEST_OPERATOR_PASSWORD)
        headers = {"Authorization": f"Bearer {auth['access_token']}"}

        purchase_response = self.client.post(
            "/api/v1/purchases",
            headers=headers,
            json={
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "1",
                "unit": "kg",
                "unit_price": "20",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat mobile",
            },
        )
        sale_response = self.client.post(
            "/api/v1/sales",
            headers=headers,
            json={
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "1",
                "unit": "kg",
                "unit_price": "90",
                "sale_date": date.today().isoformat(),
                "notes": "Vente mobile rapide",
            },
        )
        sellable_response = self.client.get(
            "/api/v1/sellable-items?kind=finished&q=Produit",
            headers=headers,
        )
        low_stock_response = self.client.get(
            "/api/v1/raw-materials?status=low",
            headers=headers,
        )
        recent_response = self.client.get(
            "/api/v1/recent-operations?kind=sale",
            headers=headers,
        )

        self.assertEqual(purchase_response.status_code, 201)
        self.assertEqual(sale_response.status_code, 201)
        self.assertEqual(sellable_response.status_code, 200)
        self.assertEqual(low_stock_response.status_code, 200)
        self.assertEqual(recent_response.status_code, 200)

        sellable_items = sellable_response.get_json()["data"]
        low_stock_items = low_stock_response.get_json()["data"]
        recent_rows = recent_response.get_json()["data"]

        self.assertTrue(any(item["key"] == f"finished:{product_id}" for item in sellable_items))
        self.assertTrue(any(int(item["id"]) == int(raw_id) for item in low_stock_items))
        self.assertTrue(any(row["operation_type"] == "sale" for row in recent_rows))
        self.assertTrue(any("Produit Mobile Rapide" in row["item_name"] for row in recent_rows))

    def test_android_wrapper_is_now_a_dedicated_mobile_client(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        index_text = (project_root / "android_wrapper" / "web" / "index.html").read_text(encoding="utf-8")
        main_text = (project_root / "android_wrapper" / "web" / "main.js").read_text(encoding="utf-8")
        readme_text = (project_root / "android_wrapper" / "README_ANDROID.md").read_text(encoding="utf-8")
        capacitor_config_text = (project_root / "android_wrapper" / "capacitor.config.json").read_text(encoding="utf-8")
        manifest_text = (project_root / "android_wrapper" / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        app_css_text = (project_root / "static" / "app.css").read_text(encoding="utf-8")
        app_js_text = (project_root / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="app"', index_text)
        self.assertIn("FABOuanes Mobile", index_text)
        self.assertIn("openFullApp", main_text)
        self.assertIn("renderFullAppLauncher", main_text)
        self.assertIn("testServerConnection", main_text)
        self.assertIn("setupRequested", main_text)
        self.assertIn("window.location.replace(fullAppUrl(path))", main_text)
        self.assertIn("application complete", main_text)
        self.assertIn("Scanner QR de l'URL", main_text)
        self.assertIn("BarcodeDetector", main_text)
        self.assertIn("qrScannerVideo", main_text)
        self.assertIn("extractServerUrl", main_text)
        self.assertIn("synchronisees avec le serveur", main_text)
        self.assertIn("pare-feu Windows autorise l'application", main_text)
        self.assertIn("leger et dedie", readme_text.lower())
        self.assertIn("ouvrir l'application web complete", readme_text.lower())
        self.assertIn("checklist reseau", readme_text.lower())
        self.assertIn('"CapacitorHttp"', capacitor_config_text)
        self.assertIn('"enabled": true', capacitor_config_text)
        self.assertIn('android:usesCleartextTraffic="true"', manifest_text)
        self.assertIn('android:networkSecurityConfig="@xml/network_security_config"', manifest_text)
        self.assertIn("android.permission.CAMERA", manifest_text)
        self.assertIn("fab-mobile-return", app_css_text)
        self.assertIn("http://localhost/?setup=1", app_js_text)
