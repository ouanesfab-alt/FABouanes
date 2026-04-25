from tests.business_flow_case import *  # noqa: F401,F403


class DashboardBusinessFlowTests(BusinessFlowTestCase):
    def test_dashboard_renders_button_switcher_sections(self) -> None:
        self._login()

        with patch.dict(os.environ, {"FAB_HOST": "127.0.0.1", "FAB_PORT": "5000"}, clear=False):
            response = self.client.get("/dashboard")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="dashboardSwitchButtons"', body)
        self.assertIn('data-fab-switch-root', body)
        self.assertIn('id="dashboardSwitchPlaceholder"', body)
        for panel_id in (
            "dashboardOperations",
            "dashboardTopDebtors",
            "dashboardLowStock",
            "dashboardRecentSales",
            "dashboardDailySummary",
            "dashboardRawMaterials",
            "dashboardFinishedProducts",
        ):
            self.assertIn(f'id="{panel_id}"', body)
            self.assertIn(f'data-fab-switch-target="{panel_id}"', body)
        self.assertEqual(body.count('class="fab-switch-btn"'), 7)
        self.assertEqual(body.count('class="card p-3 fab-switch-panel" hidden'), 7)
        self.assertIn('<th class="hide-mobile">Client</th>', body)
        self.assertIn('<th class="hide-mobile">Paye</th>', body)
        self.assertIn("Mode reseau requis", body)
        self.assertNotIn('<h1 class="dash-title">Dashboard</h1>', body)
        self.assertNotIn(">KPI</span>", body)
        self.assertNotIn(">Stocks</span>", body)
        self.assertNotIn(">Factures</span>", body)
        self.assertNotIn("data:image/png;base64,", body)

    def test_dashboard_mobile_connect_qr_uses_lan_url_in_network_mode(self) -> None:
        self._login()

        with patch.dict(os.environ, {"FAB_HOST": "0.0.0.0", "FAB_PORT": "5000", "FAB_LAN_IP": "192.168.1.76"}, clear=False):
            response = self.client.get("/dashboard")

        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Connexion mobile", body)
        self.assertIn("http://192.168.1.76:5000", body)
        self.assertIn("QR connexion mobile", body)
        self.assertIn("data:image/png;base64,", body)

    def test_dashboard_snapshot_uses_requested_target_date_for_trends(self) -> None:
        from fabouanes.core import perf_cache
        from fabouanes.repositories.dashboard_repository import get_dashboard_snapshot

        product_id = self._create_finished_product(name="Produit KPI", stock_qty=20, sale_price=0, avg_cost=10)
        self._login()

        self._post_form(
            "/sales",
            {
                "item_key": f"finished:{product_id}",
                "quantity": "1",
                "unit": "kg",
                "unit_price": "100",
                "sale_date": "2026-03-10",
                "notes": "KPI cible",
            },
            preflight_path="/sales",
        )
        self._post_form(
            "/sales",
            {
                "item_key": f"finished:{product_id}",
                "quantity": "1",
                "unit": "kg",
                "unit_price": "50",
                "sale_date": "2026-03-03",
                "notes": "KPI semaine precedente",
            },
            preflight_path="/sales",
        )

        perf_cache._CACHE.clear()
        with app.app_context():
            snapshot = get_dashboard_snapshot("2026-03-10")

        self.assertEqual(snapshot["today"], "2026-03-10")
        self.assertAlmostEqual(float(snapshot["sales_today"]), 100.0)
        self.assertEqual(snapshot["sales_delta_pct"], 100.0)
