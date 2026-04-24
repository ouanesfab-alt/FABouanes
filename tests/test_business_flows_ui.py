from tests.business_flow_case import *  # noqa: F401,F403


class UiBusinessFlowTests(BusinessFlowTestCase):
    def test_dashboard_and_transactions_compat_routes_are_available(self) -> None:
        self._login()

        dashboard_summary = self.client.get("/dashboard/summary")
        transactions = self.client.get("/transactions")
        pending = self.client.get("/transactions/pending")
        api_root = self.client.get("/api/v1")

        self.assertEqual(dashboard_summary.status_code, 200)
        self.assertEqual(transactions.status_code, 200)
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(api_root.status_code, 200)

    def test_login_allows_access_to_sales_page(self) -> None:
        self._login()

        response = self.client.get("/sales")

        self.assertEqual(response.status_code, 200)

    def test_notes_page_renders_tools_navigation_group(self) -> None:
        self._login()

        response = self.client.get("/notes")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("nav-link-menu", body)
        self.assertIn('data-bs-toggle="dropdown"', body)
        self.assertIn('<button type="button" class="nav-link-menu', body)
        self.assertIn("drawerToolsToggle", body)
        self.assertIn(">Outils<", body)
        self.assertIn("Bloc-note", body)
        self.assertIn("Lecteur PDF", body)

    def test_support_pages_render_with_clean_layouts(self) -> None:
        self._create_supplier("Fournisseur Support")
        self._login()

        routes = {
            "/transactions": "Operations",
            "/quick-add": "Type d'ajout",
            "/suppliers": "Fournisseurs",
            "/notes": "Bloc-note",
            "/pdf-reader": "Lecteur PDF",
            "/users": "Utilisateurs",
        }

        for path, marker in routes.items():
            response = self.client.get(path, follow_redirects=True)
            body = response.get_data(as_text=True)
            text = html.unescape(body)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn(marker, text)

    def test_auth_pages_use_custom_password_toggles_and_hide_native_reveal(self) -> None:
        login_response = self.client.get("/login")
        login_body = login_response.get_data(as_text=True)
        base_template = (Path(__file__).resolve().parents[1] / "templates" / "base.html").read_text(encoding="utf-8")
        app_css = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")

        self.assertEqual(login_response.status_code, 200)
        self.assertIn('id="togglePassword"', login_body)
        self.assertIn("app.css", base_template)
        self.assertIn('input[type="password"]::-ms-reveal', app_css)

        self._login()
        change_response = self.client.get("/change-password")
        change_body = change_response.get_data(as_text=True)

        self.assertEqual(change_response.status_code, 200)
        self.assertIn('data-toggle-password="currentPassword"', change_body)
        self.assertIn('data-toggle-password="newPassword"', change_body)
        self.assertIn('data-toggle-password="confirmPassword"', change_body)
        self.assertIn("Format accepte : 4 chiffres seulement.", change_body)

    def test_password_policy_requires_exactly_four_digits(self) -> None:
        ok_valid, message_valid = security.validate_password_strength("1234")
        ok_short, message_short = security.validate_password_strength("123")
        ok_alpha, message_alpha = security.validate_password_strength("12a4")
        ok_long, message_long = security.validate_password_strength("12345")

        self.assertTrue(ok_valid)
        self.assertEqual(message_valid, "")
        self.assertFalse(ok_short)
        self.assertFalse(ok_alpha)
        self.assertFalse(ok_long)
        self.assertEqual(message_short, "Le mot de passe doit contenir exactement 4 chiffres.")
        self.assertEqual(message_alpha, "Le mot de passe doit contenir exactement 4 chiffres.")
        self.assertEqual(message_long, "Le mot de passe doit contenir exactement 4 chiffres.")

    def test_mobile_bottom_nav_includes_products_tab(self) -> None:
        self._login()

        response = self.client.get("/catalog")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        base_template = (Path(__file__).resolve().parents[1] / "templates" / "base.html").read_text(encoding="utf-8")
        app_css = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")
        self.assertIn('url_for(\'catalog\')', base_template)
        self.assertIn(".bot-nav-inner > :nth-child(3){order:4;}", app_css)
        self.assertIn(".bot-nav-inner > :nth-child(4){order:3;}", app_css)
        self.assertIn(">Produits<", body)
        self.assertIn("bi-box-seam", body)

    def test_clients_page_is_simplified_and_uses_plain_table_layout(self) -> None:
        self._create_client("Client Tres Long Avec Un Nom Qui Doit Rester Lisible Dans Le Tableau")
        self._login()

        response = self.client.get("/clients")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(">Clients<", body)
        self.assertIn("Ajouter un client", body)
        self.assertIn("Importer Excel", body)
        self.assertIn("clients-table", body)
        self.assertIn('class="col-money hide-mobile">Total ventes</th>', body)
        self.assertIn("Client Tres Long Avec Un Nom Qui Doit Rester Lisible Dans Le Tableau", body)
        self.assertNotIn("Gestion clients", body)
        self.assertNotIn("Portefeuille clients", body)
        self.assertNotIn("Clique sur un client", body)
        self.assertNotIn('class="premium-hero"', body)
        self.assertNotIn('class="soft-badge', body)
        self.assertNotIn('data-table-premium"', body)

    def test_contacts_page_shows_plain_type_and_client_history_print_access(self) -> None:
        client_id = self._create_client("Client Contact Impression")
        self._login()

        contacts_response = self.client.get("/contacts")
        contacts_body = contacts_response.get_data(as_text=True)
        detail_response = self.client.get(f"/clients/{client_id}")
        detail_body = detail_response.get_data(as_text=True)
        print_response = self.client.get(f"/clients/{client_id}/print-history")
        print_body = print_response.get_data(as_text=True)
        print_text = html.unescape(print_body)

        self.assertEqual(contacts_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(print_response.status_code, 200)
        self.assertIn("contacts-page", contacts_body)
        self.assertIn("contacts-table-card", contacts_body)
        self.assertIn("Client Contact Impression", contacts_body)
        self.assertIn(f'/clients/{client_id}/print-history', contacts_body)
        self.assertIn('hide-mobile text-muted">Client</td>', contacts_body)
        self.assertNotIn('class="badge ', contacts_body)
        self.assertIn("Imprimer l'historique", detail_body)
        self.assertIn("Historique client", print_text)
        self.assertIn("Client Contact Impression", print_text)
        self.assertIn("print-doc-paper", print_body)
        self.assertIn("print-doc-party", print_body)
        self.assertIn("print-doc-partner-block", print_body)
        self.assertIn("print-doc-partner-name", print_body)
        self.assertNotIn('print-doc-card compact', print_body)
        self.assertIn(">Heure<", print_body)
        self.assertIn("Solde actuel", print_text)
        self.assertNotIn('class="invoice-shell"', print_body)

    def test_transactions_page_uses_square_type_tags_and_theme_ready_selects(self) -> None:
        supplier_id = self._create_supplier("Fournisseur Transactions Test")
        raw_id = self._create_raw_material(name="Matiere Transactions Test", stock_qty=4, avg_cost=60, sale_price=80)
        self._login()
        self.client.post(
            "/purchases/new",
            data={
                "supplier_id": str(supplier_id),
                "purchase_date": "2026-04-16",
                "notes": "",
                "raw_material_id[]": [str(raw_id)],
                "quantity[]": ["5"],
                "unit[]": ["kg"],
                "unit_price[]": ["100"],
            },
            follow_redirects=True,
        )

        response = self.client.get("/transactions")
        body = response.get_data(as_text=True)
        base_template = (Path(__file__).resolve().parents[1] / "templates" / "base.html").read_text(encoding="utf-8")
        app_css = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")
        transactions_template = (Path(__file__).resolve().parents[1] / "templates" / "transactions.html").read_text(encoding="utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("transactions-table", body)
        self.assertIn("class=\"tx-type", transactions_template)
        self.assertIn("border-radius:8px", transactions_template)
        self.assertIn("app.css", base_template)
        self.assertIn("--select-arrow:url(", app_css)
        self.assertIn("html[data-theme=\"dark\"],html[data-theme=\"midnight\"],html[data-theme=\"coffee\"]{color-scheme:dark;}", app_css)
        self.assertIn("select option,select optgroup{", app_css)
        self.assertIn("select option:checked,select option:hover,select option:focus{", app_css)

    def test_client_detail_uses_uniform_record_layout(self) -> None:
        client_id = self._create_client("Client Fiche Uniforme")
        self._login()

        response = self.client.get(f"/clients/{client_id}")
        body = response.get_data(as_text=True)
        text = html.unescape(body)

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="record-shell"', body)
        self.assertIn('class="record-surface"', body)
        self.assertIn('class="col-right hide-mobile">Prix d\'achat / credit</th>', body)
        self.assertIn("Client Fiche Uniforme", text)
        self.assertIn("Mouvements du client", text)
        self.assertIn("Imprimer l'historique", text)
        self.assertIn("Reste a payer", text)
        self.assertNotIn('class="card p-3"', body)

    def test_supplier_detail_uses_uniform_record_layout(self) -> None:
        supplier_id = self._create_supplier("Fournisseur Fiche Uniforme")
        raw_id = self._create_raw_material(name="Semoule Fiche", stock_qty=0, avg_cost=0, sale_price=0)
        self._login()

        self._post_form(
            "/purchases",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "1",
                "unit": "sac",
                "unit_price": "2000",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat fiche fournisseur",
            },
            preflight_path="/purchases",
        )

        response = self.client.get(f"/suppliers/{supplier_id}")
        body = response.get_data(as_text=True)
        text = html.unescape(body)

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="record-shell"', body)
        self.assertIn('class="record-surface"', body)
        self.assertIn('class="col-right hide-mobile">Prix unitaire</th>', body)
        self.assertIn("Fournisseur Fiche Uniforme", text)
        self.assertIn("Achats du fournisseur", text)
        self.assertIn("Montant total", text)
        self.assertIn("Semoule Fiche", text)
        self.assertNotIn('class="card p-3"', body)

    def test_sales_page_is_simplified_and_uses_plain_table_layout(self) -> None:
        client_id = self._create_client("Client Vente Avec Un Nom Tres Long Pour Tester Le Retour A La Ligne")
        product_id = self._create_finished_product(
            name="Produit Vente Avec Une Designation Assez Longue Pour Le Tableau",
            stock_qty=200,
            sale_price=120,
            avg_cost=60,
        )
        self._login()

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "5",
                "unit": "kg",
                "unit_price": "120",
                "sale_date": date.today().isoformat(),
                "notes": "Vente test",
            },
            preflight_path="/sales",
        )

        response = self.client.get("/sales")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(">Ventes<", body)
        self.assertIn("Ajouter une vente", body)
        self.assertIn("Voir les operations", body)
        self.assertIn("sales-table", body)
        self.assertIn('class="col-type hide-mobile">Type</th>', body)
        self.assertIn("Client Vente Avec Un Nom Tres Long Pour Tester Le Retour A La Ligne", body)
        self.assertIn("Produit Vente Avec Une Designation Assez Longue Pour Le Tableau", body)
        self.assertNotIn('class="premium-hero"', body)
        self.assertNotIn('class="soft-badge', body)
        self.assertNotIn('data-table-premium"', body)

    def test_purchases_page_is_simplified_and_uses_plain_table_layout(self) -> None:
        supplier_id = self._create_supplier("Fournisseur Achat Avec Un Nom Tres Long Pour Tester Le Tableau")
        raw_id = self._create_raw_material(name="Matiere Achat Avec Une Designation Longue", stock_qty=0, avg_cost=0, sale_price=0)
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
                "notes": "Achat test",
            },
            preflight_path="/purchases",
        )

        response = self.client.get("/purchases")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(">Achats<", body)
        self.assertIn("Ajouter un achat", body)
        self.assertIn("purchases-table", body)
        self.assertIn('class="col-money hide-mobile">PU</th>', body)
        self.assertIn("Fournisseur Achat Avec Un Nom Tres Long Pour Tester Le Tableau", body)
        self.assertIn("Matiere Achat Avec Une Designation Longue", body)
        self.assertNotIn('class="premium-hero"', body)
        self.assertNotIn('class="soft-badge', body)
        self.assertNotIn('data-table-premium"', body)

    def test_contact_and_operation_forms_use_uniform_clean_layout(self) -> None:
        client_id = self._create_client("Client Formulaire")
        supplier_id = self._create_supplier("Fournisseur Formulaire")
        raw_id = self._create_raw_material(name="Matiere Formulaire", stock_qty=80, avg_cost=42, sale_price=55)
        product_id = self._create_finished_product(name="Produit Formulaire", stock_qty=120, sale_price=125, avg_cost=70)
        self._login()

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "4",
                "unit": "kg",
                "unit_price": "125",
                "sale_date": date.today().isoformat(),
                "notes": "Vente formulaire",
            },
            preflight_path="/sales",
        )
        sale = self._fetchone("SELECT id FROM sales ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(sale)

        self._post_form(
            "/purchases",
            {
                "supplier_id": str(supplier_id),
                "raw_material_id": str(raw_id),
                "quantity": "3",
                "unit": "kg",
                "unit_price": "42",
                "purchase_date": date.today().isoformat(),
                "notes": "Achat formulaire",
            },
            preflight_path="/purchases",
        )
        purchase = self._fetchone("SELECT id FROM purchases ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(purchase)

        client_new_response = self.client.get("/clients/new")
        client_edit_response = self.client.get(f"/clients/{client_id}/edit")
        supplier_new_response = self.client.get("/suppliers/new")
        supplier_edit_response = self.client.get(f"/suppliers/{supplier_id}/edit")
        sale_new_response = self.client.get("/sales/new")
        sale_edit_response = self.client.get(f"/sales/finished/{int(sale['id'])}/edit")
        purchase_new_response = self.client.get("/purchases/new")
        purchase_edit_response = self.client.get(f"/purchases/{int(purchase['id'])}/edit")

        client_new_body = client_new_response.get_data(as_text=True)
        client_edit_body = client_edit_response.get_data(as_text=True)
        supplier_new_body = supplier_new_response.get_data(as_text=True)
        supplier_edit_body = supplier_edit_response.get_data(as_text=True)
        sale_new_body = sale_new_response.get_data(as_text=True)
        sale_edit_body = sale_edit_response.get_data(as_text=True)
        purchase_new_body = purchase_new_response.get_data(as_text=True)
        purchase_edit_body = purchase_edit_response.get_data(as_text=True)

        self.assertEqual(client_new_response.status_code, 200)
        self.assertEqual(client_edit_response.status_code, 200)
        self.assertEqual(supplier_new_response.status_code, 200)
        self.assertEqual(supplier_edit_response.status_code, 200)
        self.assertEqual(sale_new_response.status_code, 200)
        self.assertEqual(sale_edit_response.status_code, 200)
        self.assertEqual(purchase_new_response.status_code, 200)
        self.assertEqual(purchase_edit_response.status_code, 200)

        self.assertIn("Ajouter un client", client_new_body)
        self.assertIn("client-form-card", client_new_body)
        self.assertIn("client-form-note", client_new_body)
        self.assertNotIn('class="card p-3"', client_new_body)

        self.assertIn("Modifier le client", client_edit_body)
        self.assertIn("client-edit-card", client_edit_body)
        self.assertIn("client-edit-note", client_edit_body)
        self.assertIn("Client Formulaire", client_edit_body)
        self.assertNotIn('class="card p-4"', client_edit_body)

        self.assertIn("Ajouter un fournisseur", supplier_new_body)
        self.assertIn("supplier-form-card", supplier_new_body)
        self.assertIn("supplier-form-note", supplier_new_body)
        self.assertNotIn('class="card p-3"', supplier_new_body)

        self.assertIn("Modifier le fournisseur", supplier_edit_body)
        self.assertIn("supplier-edit-card", supplier_edit_body)
        self.assertIn("supplier-edit-note", supplier_edit_body)
        self.assertIn("Fournisseur Formulaire", supplier_edit_body)
        self.assertNotIn('class="card p-4"', supplier_edit_body)

        self.assertIn("Nouvelle vente", sale_new_body)
        self.assertIn("sale-form-card", sale_new_body)
        self.assertIn("saleStock", sale_new_body)
        self.assertIn("Stock:", sale_new_body)
        self.assertIn("Cout:", sale_new_body)
        self.assertIn("AUTRE", sale_new_body)
        self.assertIn("autre produit", sale_new_body)
        self.assertIn('data-force-unit="unite"', sale_new_body)
        self.assertIn('name="custom_item_name[]"', sale_new_body)
        self.assertIn("Preciser le produit", sale_new_body)
        self.assertNotIn("Ajoute plusieurs lignes dans un seul bon ou une seule facture.", sale_new_body)
        self.assertNotIn("Toutes les lignes ci-dessous seront enregistrees dans un seul document imprimable.", sale_new_body)
        self.assertNotIn('class="card p-3 form-compact"', sale_new_body)

        self.assertIn("Modifier une vente", sale_edit_body)
        self.assertIn("sale-edit-card", sale_edit_body)
        self.assertIn("Produit Formulaire", sale_edit_body)
        self.assertIn("Stock:", sale_edit_body)
        self.assertIn("Cout:", sale_edit_body)
        self.assertIn("AUTRE", sale_edit_body)
        self.assertIn("autre produit", sale_edit_body)
        self.assertIn('data-force-unit="unite"', sale_edit_body)
        self.assertIn('name="custom_item_name[]"', sale_edit_body)
        self.assertIn("Preciser le produit", sale_edit_body)
        self.assertNotIn("Mets a jour une facture complete sur une seule page, ligne par ligne.", sale_edit_body)
        self.assertNotIn('alert alert-light', sale_edit_body)

        self.assertIn("Nouvel achat", purchase_new_body)
        self.assertIn("purchase-form-card", purchase_new_body)
        self.assertIn("purchaseStock", purchase_new_body)
        self.assertIn("Stock:", purchase_new_body)
        self.assertIn("Cout:", purchase_new_body)
        self.assertIn("AUTRE", purchase_new_body)
        self.assertIn("autre produit", purchase_new_body)
        self.assertIn('data-force-unit="unite"', purchase_new_body)
        self.assertIn('name="custom_item_name[]"', purchase_new_body)
        self.assertIn("Preciser le produit", purchase_new_body)
        self.assertNotIn("Ajoute plusieurs matieres dans un seul bon.", purchase_new_body)
        self.assertNotIn('class="card p-3 form-compact"', purchase_new_body)

        self.assertIn("Modifier un achat", purchase_edit_body)
        self.assertIn("purchase-edit-card", purchase_edit_body)
        self.assertIn("Matiere Formulaire", purchase_edit_body)
        self.assertIn("Stock:", purchase_edit_body)
        self.assertIn("Cout:", purchase_edit_body)
        self.assertIn("AUTRE", purchase_edit_body)
        self.assertIn("autre produit", purchase_edit_body)
        self.assertIn('data-force-unit="unite"', purchase_edit_body)
        self.assertIn('name="custom_item_name[]"', purchase_edit_body)
        self.assertIn("Preciser le produit", purchase_edit_body)
        self.assertNotIn("Mets a jour un bon d'achat complet sans repasser par plusieurs formulaires.", purchase_edit_body)
        self.assertNotIn('class="card p-3"', purchase_edit_body)

    def test_catalog_page_is_simplified_and_keeps_context_actions(self) -> None:
        self._create_raw_material(name="Ble dur Tres Long Pour Tester Le Retour A La Ligne", stock_qty=125, avg_cost=42, sale_price=58)
        self._create_finished_product(
            name="Produit Final Tres Long Pour Tester La Lisibilite Dans Le Catalogue",
            default_unit="kg",
            stock_qty=45,
            sale_price=130,
            avg_cost=76,
        )
        self._login()

        response = self.client.get("/catalog")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(">Catalogue<", body)
        self.assertIn("Ajouter une matiere premiere", body)
        self.assertIn("Ajouter un produit final", body)
        self.assertIn("catalog-table", body)
        self.assertIn('class="col-type hide-mobile">Type</th>', body)
        self.assertIn("context-target", body)
        self.assertIn("Ble dur Tres Long Pour Tester Le Retour A La Ligne", body)
        self.assertIn("Produit Final Tres Long Pour Tester La Lisibilite Dans Le Catalogue", body)
        self.assertNotIn('class="premium-hero"', body)
        self.assertNotIn('class="soft-badge', body)
        self.assertNotIn('data-table-premium"', body)

    def test_catalog_product_forms_use_uniform_clean_layout(self) -> None:
        raw_id = self._create_raw_material(name="Matiere Edition")
        product_id = self._create_finished_product(name="Produit Edition")
        self._login()

        new_response = self.client.get("/catalog/new?kind=raw")
        product_edit_response = self.client.get(f"/products/{product_id}/edit")
        raw_edit_response = self.client.get(f"/raw-materials/{raw_id}/edit")

        new_body = new_response.get_data(as_text=True)
        product_edit_body = product_edit_response.get_data(as_text=True)
        raw_edit_body = raw_edit_response.get_data(as_text=True)

        self.assertEqual(new_response.status_code, 200)
        self.assertEqual(product_edit_response.status_code, 200)
        self.assertEqual(raw_edit_response.status_code, 200)

        self.assertIn("Nouvelle matiere premiere", new_body)
        self.assertIn("catalog-form-card", new_body)
        self.assertIn("catalog-form-note", new_body)
        self.assertIn("Enregistrer", new_body)
        self.assertIn("Retour", new_body)
        self.assertIn('name="category_name"', new_body)
        self.assertIn('name="custom_name"', new_body)
        self.assertIn(">AUTRE<", new_body)
        self.assertNotIn('class="premium-hero"', new_body)
        self.assertNotIn('alert alert-light', new_body)

        self.assertIn("Modifier le produit final", product_edit_body)
        self.assertIn("product-edit-card", product_edit_body)
        self.assertIn("product-edit-note", product_edit_body)
        self.assertIn("Produit Edition", product_edit_body)
        self.assertIn('name="category_name"', product_edit_body)
        self.assertIn('name="custom_name"', product_edit_body)
        self.assertIn(">AUTRE<", product_edit_body)
        self.assertNotIn('class="premium-hero"', product_edit_body)
        self.assertNotIn('alert alert-light', product_edit_body)

        self.assertIn("Modifier la matiere premiere", raw_edit_body)
        self.assertIn("raw-edit-card", raw_edit_body)
        self.assertIn("raw-edit-note", raw_edit_body)
        self.assertIn("Matiere Edition", raw_edit_body)
        self.assertIn('name="category_name"', raw_edit_body)
        self.assertIn('name="custom_name"', raw_edit_body)
        self.assertIn(">AUTRE<", raw_edit_body)
        self.assertNotIn('class="premium-hero"', raw_edit_body)
        self.assertNotIn('alert alert-light', raw_edit_body)

    def test_catalog_new_uses_custom_name_when_autre_is_selected(self) -> None:
        self._login()

        response = self._post_form(
            "/catalog/new?kind=finished",
            {
                "kind": "finished",
                "category_name": "__other__",
                "custom_name": "Produit libre interface",
                "unit": "kg",
                "stock_qty": "12",
                "sale_price": "140",
                "avg_cost": "95",
            },
            preflight_path="/catalog/new?kind=finished",
        )
        created = self._fetchone("SELECT name, stock_qty FROM finished_products ORDER BY id DESC LIMIT 1")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(created)
        self.assertEqual(created["name"], "Produit libre interface")
        self.assertEqual(float(created["stock_qty"]), 12.0)

    def test_catalog_new_keeps_selected_category_name_without_custom_field(self) -> None:
        self._login()

        response = self._post_form(
            "/catalog/new?kind=raw",
            {
                "kind": "raw",
                "category_name": "Farine",
                "custom_name": "",
                "unit": "kg",
                "stock_qty": "5",
                "avg_cost": "40",
                "sale_price": "55",
                "alert_threshold": "1",
            },
            preflight_path="/catalog/new?kind=raw",
        )
        created = self._fetchone("SELECT name, stock_qty FROM raw_materials ORDER BY id DESC LIMIT 1")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(created)
        self.assertEqual(created["name"], "Farine")
        self.assertEqual(float(created["stock_qty"]), 5.0)

    def test_catalog_edit_uses_custom_name_when_autre_is_selected(self) -> None:
        product_id = self._create_finished_product(name="Produit catalogue initial", stock_qty=8, sale_price=120, avg_cost=70)
        self._login()

        response = self._post_form(
            f"/products/{product_id}/edit",
            {
                "category_name": "__other__",
                "custom_name": "Produit catalogue precise",
                "default_unit": "Qt",
                "stock_qty": "18",
                "sale_price": "150",
                "avg_cost": "90",
            },
            preflight_path=f"/products/{product_id}/edit",
        )
        updated = self._fetchone("SELECT name, default_unit, stock_qty FROM finished_products WHERE id = ?", (product_id,))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["name"], "Produit catalogue precise")
        self.assertEqual(updated["default_unit"], "Qt")
        self.assertEqual(float(updated["stock_qty"]), 18.0)

    def test_payments_pages_use_uniform_clean_layout(self) -> None:
        client_id = self._create_client("Client Paiement Long Pour Tester Le Tableau")
        product_id = self._create_finished_product(name="Produit Paiement", stock_qty=100, sale_price=120, avg_cost=60)
        self._login()

        self._post_form(
            "/sales",
            {
                "client_id": str(client_id),
                "item_key": f"finished:{product_id}",
                "quantity": "5",
                "unit": "kg",
                "unit_price": "120",
                "sale_date": date.today().isoformat(),
                "notes": "Vente pour paiement",
            },
            preflight_path="/sales",
        )
        self._post_form(
            "/payments/new",
            {
                "client_id": str(client_id),
                "sale_link": "",
                "amount": "200",
                "payment_type": "versement",
                "payment_date": date.today().isoformat(),
                "notes": "Versement test",
                "print_after": "0",
            },
            preflight_path="/payments/new",
        )
        payment = self._fetchone("SELECT id FROM payments WHERE client_id = ? ORDER BY id DESC", (client_id,))
        self.assertIsNotNone(payment)

        list_response = self.client.get("/payments")
        new_response = self.client.get("/payments/new")
        edit_response = self.client.get(f"/payments/{int(payment['id'])}/edit")

        list_body = list_response.get_data(as_text=True)
        new_body = new_response.get_data(as_text=True)
        edit_body = edit_response.get_data(as_text=True)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(new_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 200)

        self.assertIn(">Paiements<", list_body)
        self.assertIn("Ajouter un versement", list_body)
        self.assertIn("Ajouter une avance", list_body)
        self.assertIn("payments-table", list_body)
        self.assertIn('class="col-ref hide-mobile">Reference</th>', list_body)
        self.assertIn("Client Paiement Long Pour Tester Le Tableau", list_body)
        self.assertNotIn('class="premium-hero"', list_body)

        self.assertIn("Enregistrer un versement", new_body)
        self.assertIn("payment-form-card", new_body)
        self.assertIn("payment-form-note", new_body)
        self.assertNotIn('class="premium-hero"', new_body)

        self.assertIn("Modifier une transaction client", edit_body)
        self.assertIn("payment-edit-card", edit_body)
        self.assertIn("payment-edit-note", edit_body)
        self.assertNotIn('class="premium-hero"', edit_body)

    def test_production_pages_use_uniform_clean_layout(self) -> None:
        raw_a_id = self._create_raw_material(name="Ble production", stock_qty=100, avg_cost=20, sale_price=25)
        raw_b_id = self._create_raw_material(name="Additif production", stock_qty=40, avg_cost=30, sale_price=35)
        product_id = self._create_finished_product(name="Produit production", stock_qty=0, sale_price=0, avg_cost=0)
        self._login()

        self._post_form(
            "/production/new",
            {
                "finished_product_id": str(product_id),
                "output_quantity": "10",
                "production_date": date.today().isoformat(),
                "notes": "Production test interface",
                "recipe_name": "Recette interface",
                "save_recipe": "0",
                "print_after": "0",
                "raw_material_id[]": [str(raw_a_id), str(raw_b_id)],
                "quantity[]": ["20", "10"],
            },
            preflight_path="/production/new",
        )

        list_response = self.client.get("/production")
        new_response = self.client.get("/production/new")

        list_body = list_response.get_data(as_text=True)
        new_body = new_response.get_data(as_text=True)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(new_response.status_code, 200)

        self.assertIn(">Production<", list_body)
        self.assertIn("Ajouter une production", list_body)
        self.assertIn("production-table", list_body)
        self.assertIn('class="col-recipe hide-mobile">Recette</th>', list_body)
        self.assertIn("Produit production", list_body)
        self.assertIn("Ble production", list_body)
        self.assertIn("editProdSheet", list_body)
        self.assertNotIn('class="premium-hero"', list_body)

        self.assertIn("Nouvelle production", new_body)
        self.assertIn("production-form-card", new_body)
        self.assertIn("production-metrics", new_body)
        self.assertIn("production-form-note", new_body)
        self.assertIn("ingredientRows", new_body)
        self.assertNotIn('class="premium-hero"', new_body)
