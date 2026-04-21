from tests.business_flow_case import *  # noqa: F401,F403


class PrintBusinessFlowTests(BusinessFlowTestCase):
    def test_shared_print_documents_render_new_html_and_pdf_layout(self) -> None:
        if not REPORTLAB_AVAILABLE:
            self.skipTest("ReportLab is not available in this environment.")

        supplier_id = self._create_supplier("Fournisseur Impression")
        client_id = self._create_client("Client Impression")
        raw_id = self._create_raw_material(name="Semoule impression", stock_qty=0, avg_cost=0, sale_price=0)
        product_id = self._create_finished_product(
            name="Produit impression",
            stock_qty=120,
            sale_price=150,
            avg_cost=80,
        )
        self._login()

        self._post_form(
            "/purchases",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "4",
                "unit": "sac",
                "unit_price": "2500",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat impression",
            },
            preflight_path="/purchases",
        )
        purchase = self._fetchone("SELECT id FROM purchases ORDER BY id DESC", ())
        self.assertIsNotNone(purchase)

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "5",
                "unit": "kg",
                "unit_price": "150",
                "sale_date": date.today().isoformat(),
                "notes": "Vente produit imprimee",
            },
            preflight_path="/sales",
        )
        sale_finished = self._fetchone("SELECT id FROM sales ORDER BY id DESC", ())
        self.assertIsNotNone(sale_finished)

        self._post_form(
            "/sales",
            {
                "item_key": f"raw:{raw_id}",
                "quantity": "8",
                "unit": "kg",
                "unit_price": "75",
                "sale_date": date.today().isoformat(),
                "notes": "",
            },
            preflight_path="/sales",
        )
        sale_raw = self._fetchone("SELECT id FROM raw_sales ORDER BY id DESC", ())
        self.assertIsNotNone(sale_raw)

        self._post_form(
            "/payments",
            {
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "300",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement impression",
            },
            preflight_path="/payments",
        )
        payment = self._fetchone("SELECT id FROM payments ORDER BY id DESC", ())
        self.assertIsNotNone(payment)

        self._post_form(
            "/production/new",
            {
                "finished_product_id": str(product_id),
                "output_quantity": "10",
                "production_date": date.today().isoformat(),
                "notes": "Production impression",
                "recipe_name": "Recette impression",
                "save_recipe": "0",
                "raw_material_id[]": [str(raw_id)],
                "quantity[]": ["20"],
            },
            preflight_path="/production/new",
        )
        production = self._fetchone("SELECT id FROM production_batches ORDER BY id DESC", ())
        self.assertIsNotNone(production)

        documents = {
            "purchase": {
                "id": int(purchase["id"]),
                "title": "Bon d'achat",
                "partner": "Fournisseur Impression",
                "number_prefix": "ACH-",
            },
            "sale_finished": {
                "id": int(sale_finished["id"]),
                "title": "Facture",
                "partner": "Client Impression",
                "number_prefix": "VPF-",
            },
            "sale_raw": {
                "id": int(sale_raw["id"]),
                "title": "Facture",
                "partner": "Comptoir",
                "number_prefix": "VMP-",
            },
            "payment": {
                "id": int(payment["id"]),
                "title": "Re\u00e7u",
                "partner": "Client Impression",
                "number_prefix": "PAY-",
            },
            "production": {
                "id": int(production["id"]),
                "title": "Fiche de production",
                "partner": "Produit impression",
                "number_prefix": "PROD-",
            },
        }

        for doc_type, expected in documents.items():
            html_response = self.client.get(f"/print/{doc_type}/{expected['id']}")
            html_body = html_response.get_data(as_text=True)
            html_text = html.unescape(html_body)

            self.assertEqual(html_response.status_code, 200)
            self.assertIn("print-doc-paper", html_body)
            self.assertIn("print-doc-logo", html_body)
            self.assertIn("print-doc-header-table", html_body)
            self.assertIn("print-doc-reference", html_body)
            self.assertIn("print-doc-partner-table", html_body)
            self.assertIn("print-doc-partner-block", html_body)
            self.assertIn("print-doc-partner-name", html_body)
            self.assertIn("print-doc-info-meta", html_body)
            self.assertIn("print-doc-meta-table", html_body)
            self.assertNotIn('print-doc-card compact', html_body)
            self.assertNotIn("print-doc-company", html_body)
            self.assertNotIn('class="bot-nav"', html_body)
            self.assertNotIn('class="fab-mobile-return"', html_body)
            self.assertIn(expected["title"], html_text)
            self.assertIn(expected["partner"], html_text)
            self.assertIn(expected["number_prefix"], html_text)
            self.assertIn(">Reference<", html_body)
            self.assertIn(">Date<", html_body)
            self.assertIn(">Heure<", html_body)
            self.assertIn(">Total<", html_body)
            if doc_type == "sale_finished":
                self.assertIn("Vente produit final", html_text)
            self.assertNotIn("Observations", html_body)

            pdf_response = self.client.get(f"/print/{doc_type}/{expected['id']}?format=pdf")
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(pdf_response.mimetype, "application/pdf")
            self.assertTrue(pdf_response.get_data().startswith(b"%PDF"))

        project_root = Path(__file__).resolve().parents[1]
        print_template = (project_root / "templates" / "print_document.html").read_text(encoding="utf-8")
        print_route_text = (project_root / "fabouanes" / "routes" / "print_routes.py").read_text(encoding="utf-8")
        print_service_text = (project_root / "fabouanes" / "services" / "print_service.py").read_text(encoding="utf-8")

        self.assertIn(".print-doc-shell{width:min(100%,var(--print-content-width));max-width:var(--print-content-width);", print_template)
        self.assertIn("@page{size:A4 portrait;margin:{{ print_layout.page_margin_mm }}mm;}", print_template)
        self.assertIn("--print-screen-scale:{{ print_layout.screen_scale }};", print_template)
        self.assertIn("@media screen and (min-width:768px){", print_template)
        self.assertIn(".print-doc-shell{zoom:var(--print-screen-scale);}", print_template)
        self.assertIn(".print-doc-table thead{display:table-header-group;}", print_template)
        self.assertIn(".print-doc-table tbody tr{break-inside:avoid-page;page-break-inside:avoid;}", print_template)
        self.assertIn("print_layout=PRINT_LAYOUT", print_route_text)
        self.assertIn('"page_width_mm": 210', print_service_text)
        self.assertIn('"page_margin_mm": 10', print_service_text)
        self.assertIn('"screen_scale": 1.0', print_service_text)
        self.assertIn("topMargin=PDF_PAGE_MARGIN_CM * cm", print_service_text)
        self.assertIn("leftMargin=PDF_PAGE_MARGIN_CM * cm", print_service_text)
