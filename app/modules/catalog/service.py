from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from app.core.models import RawMaterial, FinishedProduct, SavedRecipe, SavedRecipeItem
from app.core.events import DomainEvent, emit
from app.core.perf_cache import async_cached_result, invalidate_cache_domains
from app.core.helpers import refresh_sale_profits_for_item, unit_choices
from app.utils.pagination import paginate_sequence
from app.modules.catalog.repository import RawMaterialRepository, FinishedProductRepository, SavedRecipeRepository
from app.modules.catalog.schemas_validation import (
    RawMaterialCreateSchema,
    RawMaterialUpdateSchema,
    FinishedProductCreateSchema,
    FinishedProductUpdateSchema,
)

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


class CatalogService:
    """Asynchronous business service layer for the Catalog module."""

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

        # Cache the slow database queries (velocity computations)
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
            # Calculate days left
            v = raw_velocities.get(rm.id, 0.0)
            item["days_left"] = int(round(float(rm.stock_qty) / v)) if v > 0.001 else None

            # Proactive alerts
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
            # Calculate days left
            v = finished_velocities.get(fp.id, 0.0)
            item["days_left"] = int(round(float(fp.stock_qty) / v)) if v > 0.001 else None

            # Proactive alerts
            item["is_low"] = item["days_left"] is not None and item["days_left"] <= 7
            if item["is_low"]:
                item["autonomy_status"] = "CRITICAL"
            elif item["days_left"] is not None and item["days_left"] <= 14:
                item["autonomy_status"] = "WARNING"
            else:
                item["autonomy_status"] = "OK"

            finished_items_dict.append(item)
            all_products.append(item)

        # Sort all products combined
        all_products = sorted(all_products, key=lambda row: (row["kind"], row["name"]))

        return {
            "raw_items": raw_items_dict,
            "finished_items": finished_items_dict,
            "all_products": all_products,
        }

    async def create_raw_material(self, schema: RawMaterialCreateSchema) -> RawMaterial:
        rm = RawMaterial(
            name=schema.name,
            unit=schema.unit,
            stock_qty=schema.stock_qty,
            avg_cost=schema.avg_cost,
            sale_price=schema.sale_price,
            alert_threshold=schema.alert_threshold,
            threshold_qty=schema.alert_threshold,  # Backwards compatibility key
        )
        created = await self.raw_repo.create(rm)
        invalidate_cache_domains("catalog")

        emit(
            DomainEvent(
                "create",
                "raw_material",
                created.id,
                created.name,
                after=created.model_dump(),
            )
        )
        return created

    async def create_finished_product(self, schema: FinishedProductCreateSchema) -> FinishedProduct:
        fp = FinishedProduct(
            name=schema.name,
            default_unit=schema.default_unit,
            stock_qty=schema.stock_qty,
            sale_price=schema.sale_price,
            avg_cost=schema.avg_cost,
        )
        created = await self.finished_repo.create(fp)
        invalidate_cache_domains("catalog")

        emit(
            DomainEvent(
                "create",
                "finished_product",
                created.id,
                created.name,
                after=created.model_dump(),
            )
        )
        return created

    async def update_raw_material(self, material_id: int, schema: RawMaterialUpdateSchema) -> Optional[RawMaterial]:
        rm = await self.raw_repo.get_by_id(material_id)
        if not rm:
            return None

        before_dump = rm.model_dump()
        rm.name = schema.name
        rm.unit = schema.unit
        rm.stock_qty = schema.stock_qty
        rm.avg_cost = schema.avg_cost
        rm.sale_price = schema.sale_price
        rm.alert_threshold = schema.alert_threshold
        rm.threshold_qty = schema.alert_threshold

        updated = await self.raw_repo.update(rm)
        invalidate_cache_domains("catalog")

        # Refresh profit snapshots asynchronously in a background thread
        await asyncio.to_thread(
            refresh_sale_profits_for_item,
            "raw",
            material_id,
            schema.avg_cost,
            schema.sale_price
        )

        emit(
            DomainEvent(
                "update",
                "raw_material",
                material_id,
                f"{updated.name} | achat={updated.avg_cost} | vente={updated.sale_price}",
                before=before_dump,
                after=updated.model_dump(),
            )
        )
        return updated

    async def update_finished_product(self, product_id: int, schema: FinishedProductUpdateSchema) -> Optional[FinishedProduct]:
        fp = await self.finished_repo.get_by_id(product_id)
        if not fp:
            return None

        before_dump = fp.model_dump()
        fp.name = schema.name
        fp.default_unit = schema.default_unit
        fp.stock_qty = schema.stock_qty
        fp.sale_price = schema.sale_price
        fp.avg_cost = schema.avg_cost

        updated = await self.finished_repo.update(fp)
        invalidate_cache_domains("catalog")

        # Refresh profit snapshots asynchronously
        await asyncio.to_thread(
            refresh_sale_profits_for_item,
            "finished",
            product_id,
            schema.avg_cost,
            schema.sale_price
        )

        emit(
            DomainEvent(
                "update",
                "finished_product",
                product_id,
                f"{updated.name} | revient={updated.avg_cost} | vente={updated.sale_price}",
                before=before_dump,
                after=updated.model_dump(),
            )
        )
        return updated

    async def delete_raw_material(self, material_id: int) -> bool:
        rm = await self.raw_repo.get_by_id(material_id)
        if not rm:
            return False

        if await self.raw_repo.is_linked(material_id):
            return False

        before_dump = rm.model_dump()
        success = await self.raw_repo.delete(material_id)

        if success:
            invalidate_cache_domains("catalog")
            emit(
                DomainEvent(
                    "delete",
                    "raw_material",
                    material_id,
                    "Suppression matière",
                    before=before_dump,
                )
            )
        return success

    async def delete_finished_product(self, product_id: int) -> bool:
        fp = await self.finished_repo.get_by_id(product_id)
        if not fp:
            return False

        if await self.finished_repo.is_linked(product_id):
            return False

        before_dump = fp.model_dump()
        success = await self.finished_repo.delete(product_id)

        if success:
            invalidate_cache_domains("catalog")
            emit(
                DomainEvent(
                    "delete",
                    "finished_product",
                    product_id,
                    "Suppression produit",
                    before=before_dump,
                )
            )
        return success

    # --- RECIPE SERVICES ---

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

    async def save_recipe_definition(
        self,
        finished_product_id: int,
        name: str,
        notes: str,
        items: List[Dict[str, Any]],
        user_id: int | None = None,
    ) -> Optional[int]:
        clean_name = (name or "").strip()
        if not clean_name or not items:
            return None

        # Look up existing recipe
        existing = await self.recipe_repo.find_by_product_and_name(finished_product_id, clean_name)
        if existing:
            recipe_id = existing.id
            existing.notes = notes
            existing.created_by_user_id = existing.created_by_user_id or user_id
            await self.recipe_repo.update(existing)
            await self.recipe_repo.delete_recipe_items(recipe_id)
        else:
            recipe = SavedRecipe(
                finished_product_id=finished_product_id,
                name=clean_name,
                notes=notes,
                created_by_user_id=user_id,
            )
            created = await self.recipe_repo.create(recipe)
            recipe_id = created.id

        # Insert recipe items
        for pos, item_data in enumerate(items, start=1):
            recipe_item = SavedRecipeItem(
                recipe_id=recipe_id,
                raw_material_id=int(item_data["raw_material_id"]),
                quantity=float(item_data["quantity"]),
                position=pos,
            )
            await self.recipe_repo.add_recipe_item(recipe_item)

        await self.session.commit()
        return recipe_id


# Helper methods for controller/route templates mapping

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
