from tests.business_flow_case import *  # noqa: F401,F403


class ProductionBusinessFlowTests(BusinessFlowTestCase):
    def test_production_creation_and_deletion_restore_stocks(self) -> None:
        raw_a_id = self._create_raw_material(name="Ble dur", stock_qty=100, avg_cost=20, sale_price=25)
        raw_b_id = self._create_raw_material(name="Additif", stock_qty=40, avg_cost=30, sale_price=35)
        product_id = self._create_finished_product(name="Couscous", stock_qty=0, sale_price=0, avg_cost=0)
        self._login()

        create_response = self._post_form(
            "/production/new",
            {
                "finished_product_id": str(product_id),
                "output_quantity": "10",
                "production_date": date.today().isoformat(),
                "notes": "Production test",
                "recipe_name": "Recette test",
                "save_recipe": "0",
                "raw_material_id[]": [str(raw_a_id), str(raw_b_id)],
                "quantity[]": ["20", "10"],
            },
            preflight_path="/production/new",
        )

        self.assertEqual(create_response.status_code, 200)
        batch = self._fetchone(
            "SELECT id, output_quantity, production_cost, unit_cost FROM production_batches WHERE finished_product_id = ? ORDER BY id DESC",
            (product_id,),
        )
        raw_a = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_a_id,))
        raw_b = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_b_id,))
        product = self._fetchone("SELECT stock_qty, avg_cost, sale_price FROM finished_products WHERE id = ?", (product_id,))
        self.assertIsNotNone(batch)
        self.assertAlmostEqual(float(batch["output_quantity"]), 10.0)
        self.assertAlmostEqual(float(batch["production_cost"]), 700.0)
        self.assertAlmostEqual(float(batch["unit_cost"]), 70.0)
        self.assertAlmostEqual(float(raw_a["stock_qty"]), 80.0)
        self.assertAlmostEqual(float(raw_b["stock_qty"]), 30.0)
        self.assertAlmostEqual(float(product["stock_qty"]), 10.0)
        self.assertAlmostEqual(float(product["avg_cost"]), 70.0)
        self.assertAlmostEqual(float(product["sale_price"]), 80.5)

        delete_response = self._post_form(
            f"/production/{int(batch['id'])}/delete",
            {},
            preflight_path="/production",
        )

        self.assertEqual(delete_response.status_code, 200)
        raw_a_after_delete = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_a_id,))
        raw_b_after_delete = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_b_id,))
        product_after_delete = self._fetchone("SELECT stock_qty, avg_cost FROM finished_products WHERE id = ?", (product_id,))
        deleted_batch = self._fetchone("SELECT id FROM production_batches WHERE id = ?", (int(batch["id"]),))
        self.assertAlmostEqual(float(raw_a_after_delete["stock_qty"]), 100.0)
        self.assertAlmostEqual(float(raw_b_after_delete["stock_qty"]), 40.0)
        self.assertAlmostEqual(float(product_after_delete["stock_qty"]), 0.0)
        self.assertAlmostEqual(float(product_after_delete["avg_cost"]), 0.0)
        self.assertIsNone(deleted_batch)

    def test_new_production_rolls_back_when_recipe_save_fails(self) -> None:
        raw_id = self._create_raw_material(name="Ble dur", stock_qty=100, avg_cost=20, sale_price=25)
        product_id = self._create_finished_product(name="Couscous", stock_qty=0, sale_price=0, avg_cost=0)
        self._login()

        with self.assertLogs(app.logger.name, level="ERROR"):
            with patch("fabouanes.services.production_service.save_recipe_definition", side_effect=RuntimeError("boom")):
                response = self._post_form(
                    "/production/new",
                    {
                        "finished_product_id": str(product_id),
                        "output_quantity": "10",
                        "production_date": date.today().isoformat(),
                        "notes": "Production test",
                        "recipe_name": "Recette test",
                        "save_recipe": "1",
                        "raw_material_id[]": [str(raw_id)],
                        "quantity[]": ["20"],
                    },
                    preflight_path="/production/new",
                )

        self.assertEqual(response.status_code, 200)
        batch_count = self._scalar("SELECT COUNT(*) FROM production_batches WHERE finished_product_id = ?", (product_id,))
        batch_item_count = self._scalar("SELECT COUNT(*) FROM production_batch_items", ())
        raw_after = self._fetchone("SELECT stock_qty FROM raw_materials WHERE id = ?", (raw_id,))
        product_after = self._fetchone("SELECT stock_qty, avg_cost, sale_price FROM finished_products WHERE id = ?", (product_id,))
        self.assertEqual(int(batch_count), 0)
        self.assertEqual(int(batch_item_count), 0)
        self.assertAlmostEqual(float(raw_after["stock_qty"]), 100.0)
        self.assertAlmostEqual(float(product_after["stock_qty"]), 0.0)
        self.assertAlmostEqual(float(product_after["avg_cost"]), 0.0)
        self.assertAlmostEqual(float(product_after["sale_price"]), 0.0)
