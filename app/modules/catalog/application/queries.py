from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from app.core.models import RawMaterial, FinishedProduct
from app.core.perf_cache import async_cached_result
from app.core.helpers import unit_choices
from app.utils.pagination import paginate_sequence
from app.modules.catalog.infrastructure.repository import RawMaterialRepository, FinishedProductRepository, SavedRecipeRepository

# Constants
RAW_MATERIAL_PRESETS = [
    "Maïs",
    "Orge",
    "Son",
    "Soya",
    "CMV",
    "Phosphate",
    "Soja",
    "Son de blé",
    "Concentré",
    "Sel",
    "Carbonate",
    "Sac vide (50kg)",
    "Sac vide (25kg)"
]

FINISHED_PRODUCT_PRESETS = [
    "Aliment Démarrage",
    "Aliment Croissance",
    "Aliment Finition",
    "Aliment Pondeuse",
    "Aliment Vache Laitière",
    "Aliment Engraissement",
    "Aliment Démarrage (Sac 50kg)",
    "Aliment Croissance (Sac 50kg)",
    "Aliment Finition (Sac 50kg)",
    "Aliment Pondeuse (Sac 50kg)",
    "Aliment Vache Laitière (Sac 50kg)",
    "Aliment Engraissement (Sac 50kg)",
    "Poussin d'un jour",
    "Poussin Chair",
    "Poussin Pondeuse",
    "Oeufs (Plateau 30)"
]


def quick_add_context(default_target: str = "client") -> dict:
    return {
        "default_target": default_target,
        "options": [
            ("client", "Client", "/contacts/clients/new"),
            ("supplier", "Fournisseur", "/contacts/suppliers/new"),
            ("product_raw", "Matière première", "/catalog/new?kind=raw"),
            ("product_finished", "Produit fini", "/catalog/new?kind=finished"),
            ("purchase", "Achat", "/operations/purchases/new"),
            ("sale", "Vente", "/operations/sales/new"),
            ("production", "Production", "/production/new"),
            ("payment", "Versement", "/operations/payments/new"),
            ("advance", "Avance", "/operations/payments/new?mode=avance"),
        ],
    }


def new_catalog_context(kind: str = "raw") -> dict:
    return {
        "kind": "finished" if kind == "finished" else "raw",
        "units": unit_choices(),
        "raw_presets": RAW_MATERIAL_PRESETS,
        "finished_presets": FINISHED_PRODUCT_PRESETS,
        "other_category_value": "__other__",
        "custom_name_value": ""
    }


def resolve_name_from_form(form: dict | Any, kind: str = None) -> str:
    name = str(form.get("name", "")).strip()
    if not kind:
        kind = str(form.get("kind", "raw")).strip()
    presets = RAW_MATERIAL_PRESETS if kind == "raw" else FINISHED_PRODUCT_PRESETS
    if not name:
        return "autre"
    if name in presets:
        return name
    lower_name = name.lower()
    if lower_name.startswith("autre:"):
        return name
    elif lower_name.startswith("autre :"):
        return f"autre: {name[7:].strip()}"
    else:
        return f"autre: {name}"


def raw_material_edit_context(material: RawMaterial) -> dict:
    name = material.name
    is_preset = name in RAW_MATERIAL_PRESETS
    if is_preset:
        custom_val = name
    else:
        lower_name = name.lower()
        if lower_name.startswith("autre:"):
            custom_val = name[6:].strip()
        elif lower_name.startswith("autre :"):
            custom_val = name[7:].strip()
        else:
            custom_val = name
    return {
        "material": {
            "id": material.id,
            "name": material.name,
            "unit": material.unit,
            "stock_qty": material.stock_qty,
            "avg_cost": material.avg_cost,
            "sale_price": material.sale_price,
            "alert_threshold": material.alert_threshold,
        },
        "units": unit_choices(),
        "name_presets": RAW_MATERIAL_PRESETS,
        "custom_name_value": custom_val
    }


def product_edit_context(product: FinishedProduct) -> dict:
    name = product.name
    is_preset = name in FINISHED_PRODUCT_PRESETS
    if is_preset:
        custom_val = name
    else:
        lower_name = name.lower()
        if lower_name.startswith("autre:"):
            custom_val = name[6:].strip()
        elif lower_name.startswith("autre :"):
            custom_val = name[7:].strip()
        else:
            custom_val = name
    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "default_unit": product.default_unit,
            "stock_qty": product.stock_qty,
            "sale_price": product.sale_price,
            "avg_cost": product.avg_cost,
        },
        "units": unit_choices(),
        "name_presets": FINISHED_PRODUCT_PRESETS,
        "custom_name_value": custom_val
    }


class CatalogQueries:
    """Gestion des requêtes en lecture seule (Queries) du module Catalogue."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.raw_repo = RawMaterialRepository(session)
        self.finished_repo = FinishedProductRepository(session)
        self.recipe_repo = SavedRecipeRepository(session)

    async def get_raw_material(self, material_id: int) -> Optional[RawMaterial]:
        return await self.raw_repo.get_by_id(material_id)

    async def get_product(self, product_id: int) -> Optional[FinishedProduct]:
        return await self.finished_repo.get_by_id(product_id)

    async def catalog_context(self, args: dict = None, path: str = "/catalog") -> dict:
        search = str((args or {}).get("q", "") or "").strip()
        kind_filter = str((args or {}).get("kind", "all") or "all").strip().lower()
        if kind_filter not in {"all", "raw", "finished"}:
            kind_filter = "all"

        base = await async_cached_result(
            ("catalog_context",),
            self._build_catalog_context,
            ttl_seconds=6.0
        )

        products = list(base["all_products"])
        if kind_filter == "raw":
            products = [row for row in products if row.get("row_kind") == "raw"]
        elif kind_filter == "finished":
            products = [row for row in products if row.get("row_kind") == "finished"]

        if search:
            needle = search.lower()
            products = [
                row for row in products
                if needle in f"{row['name']} {row['unit']} {row['kind']}".lower()
            ]

        page_products, pagination = paginate_sequence(products, args or {}, path)

        return {
            "raw_items": [row for row in page_products if row.get("row_kind") == "raw"],
            "finished_items": [row for row in page_products if row.get("row_kind") == "finished"],
            "all_products": page_products,
            "catalog_filters": {"q": search, "kind": kind_filter},
            "pagination": pagination,
        }

    async def _build_catalog_context(self) -> dict:
        cutoff_date = date.today() - timedelta(days=30)

        raw_velocities = await self.raw_repo.get_30d_velocities(cutoff_date)
        finished_velocities = await self.finished_repo.get_30d_velocities(cutoff_date)
        raw_materials = await self.raw_repo.get_all_ordered()
        finished_products = await self.finished_repo.get_all_ordered()

        raw_items_dict = []
        finished_items_dict = []
        all_products = []

        for rm in raw_materials:
            item = {
                "id": rm.id,
                "name": rm.name,
                "unit": rm.unit,
                "stock_qty": rm.stock_qty,
                "avg_cost": rm.avg_cost,
                "sale_price": rm.sale_price,
                "alert_threshold": rm.alert_threshold,
                "threshold_qty": rm.threshold_qty,
                "kind": "Matière première",
                "row_kind": "raw"
            }
            v = raw_velocities.get(rm.id, 0.0)
            item["days_left"] = int(round(float(rm.stock_qty) / v)) if v > 0.001 else None

            threshold = float(rm.threshold_qty or rm.alert_threshold or 0)
            is_below_threshold = float(rm.stock_qty) <= threshold

            item["is_low"] = is_below_threshold or (item["days_left"] is not None and item["days_left"] <= 7)
            if item["is_low"]:
                item["autonomy_status"] = "CRITICAL"
            elif item["days_left"] is not None and item["days_left"] <= 14:
                item["autonomy_status"] = "WARNING"
            else:
                item["autonomy_status"] = "OK"

            raw_items_dict.append(item)
            all_products.append(item)

        for fp in finished_products:
            item = {
                "id": fp.id,
                "name": fp.name,
                "unit": fp.default_unit,
                "stock_qty": fp.stock_qty,
                "avg_cost": fp.avg_cost,
                "sale_price": fp.sale_price,
                "kind": "Produit fini",
                "row_kind": "finished"
            }
            v = finished_velocities.get(fp.id, 0.0)
            item["days_left"] = int(round(float(fp.stock_qty) / v)) if v > 0.001 else None

            item["is_low"] = item["days_left"] is not None and item["days_left"] <= 7
            if item["is_low"]:
                item["autonomy_status"] = "CRITICAL"
            elif item["days_left"] is not None and item["days_left"] <= 14:
                item["autonomy_status"] = "WARNING"
            else:
                item["autonomy_status"] = "OK"

            finished_items_dict.append(item)
            all_products.append(item)

        all_products = sorted(all_products, key=lambda row: (row["kind"], row["name"]))

        return {
            "raw_items": raw_items_dict,
            "finished_items": finished_items_dict,
            "all_products": all_products,
        }

    async def load_saved_recipes(self) -> List[Dict[str, Any]]:
        recipes = await self.recipe_repo.get_all_with_products()
        if not recipes:
            return []

        item_rows = await self.recipe_repo.get_recipe_items()
        grouped = defaultdict(list)
        for row in item_rows:
            grouped[int(row["recipe_id"])].append(
                {
                    "raw_material_id": int(row["raw_material_id"]),
                    "quantity": float(row["quantity"]),
                    "material_name": row["material_name"],
                    "stock_qty": float(row["stock_qty"]),
                    "unit": row["unit"],
                }
            )

        for recipe in recipes:
            recipe["items"] = grouped.get(int(recipe["id"]), [])
        return recipes
