# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
import os
from typing import Any, Dict
from app.core.config import BASE_DIR
from app.modules.assistant.tool_actions import sanitize_numeric, _assert_workspace_path

logger = logging.getLogger("fabouanes.assistant")

async def handle_catalog(func_name: str, func_args: dict, session_maker, user_role: str = 'operator') -> Dict[str, Any] | None:

    if func_name == "add_product":
            name = str(func_args.get("name", "")).strip().title()
            category = str(func_args.get("category", "")).strip().lower()
            price = sanitize_numeric(func_args.get("price"))
            cost = sanitize_numeric(func_args.get("cost"))
            unit = str(func_args.get("unit", "kg")).strip().lower()
            stock_qty = sanitize_numeric(func_args.get("stock_qty", 0.0))
            alert_threshold = sanitize_numeric(func_args.get("alert_threshold", 0.0))
            is_finished = category in ("finished", "produit final", "produit")
            from app.modules.catalog.application.services import CatalogService
            from app.modules.catalog.api.schemas import FinishedProductCreateSchema, RawMaterialCreateSchema
            async with session_maker() as session:
                service = CatalogService(session)
                if is_finished:
                    product = await service.create_finished_product(FinishedProductCreateSchema(
                        name=name,
                        sale_price=price,
                        avg_cost=cost,
                        default_unit=unit,
                        stock_qty=stock_qty,
                    ))
                else:
                    product = await service.create_raw_material(RawMaterialCreateSchema(
                        name=name,
                        avg_cost=cost,
                        sale_price=price,
                        unit=unit,
                        stock_qty=stock_qty,
                        alert_threshold=alert_threshold,
                    ))
                prod_id = product.id
                await session.commit()
            return {"success": True, "message": f"Produit {name} ajouté.", "product_id": prod_id}

    elif func_name == "modify_product":
            product_id = int(func_args.get("product_id"))
            category = str(func_args.get("category", "finished")).strip().lower()
            name = func_args.get("name")
            if name:
                name = str(name).strip().title()
            price = func_args.get("price")
            if price is not None:
                price = sanitize_numeric(price)
            cost = func_args.get("cost")
            if cost is not None:
                cost = sanitize_numeric(cost)
            unit = str(func_args.get("unit", "")).strip().lower()
            stock_qty = func_args.get("stock_qty")
            if stock_qty is not None:
                stock_qty = sanitize_numeric(stock_qty)
            alert_threshold = func_args.get("alert_threshold")
            if alert_threshold is not None:
                alert_threshold = sanitize_numeric(alert_threshold)
            is_finished = category in ("finished", "produit final", "produit")
            from app.modules.catalog.application.services import CatalogService
            from app.modules.catalog.api.schemas import FinishedProductUpdateSchema, RawMaterialUpdateSchema
            async with session_maker() as session:
                service = CatalogService(session)
                if is_finished:
                    existing = await service.get_product(product_id)
                    if not existing:
                        return {"error": f"Produit fini {product_id} introuvable."}
                    updated = await service.update_finished_product(product_id, FinishedProductUpdateSchema(
                        name=name or existing.name,
                        default_unit=unit if "unit" in func_args else existing.default_unit,
                        stock_qty=stock_qty if stock_qty is not None else existing.stock_qty,
                        sale_price=price if price is not None else existing.sale_price,
                        avg_cost=cost if cost is not None else existing.avg_cost,
                    ))
                else:
                    existing = await service.get_raw_material(product_id)
                    if not existing:
                        return {"error": f"Matiere premiere {product_id} introuvable."}
                    updated = await service.update_raw_material(product_id, RawMaterialUpdateSchema(
                        name=name or existing.name,
                        unit=unit if "unit" in func_args else existing.unit,
                        stock_qty=stock_qty if stock_qty is not None else existing.stock_qty,
                        avg_cost=cost if cost is not None else existing.avg_cost,
                        sale_price=price if price is not None else existing.sale_price,
                        alert_threshold=alert_threshold if alert_threshold is not None else existing.alert_threshold,
                    ))
                await session.commit()
            if not updated:
                return {"error": f"Produit {product_id} introuvable ou non modifie."}
            return {"success": True, "message": f"Produit {product_id} modifié."}

    elif func_name == "delete_product":
            product_id = int(func_args.get("product_id"))
            category = func_args.get("category", "finished")
            is_finished = category.lower() in ("finished", "produit final", "produit")
            from app.modules.catalog.application.services import CatalogService
            async with session_maker() as session:
                service = CatalogService(session)
                success = await (
                    service.delete_finished_product(product_id)
                    if is_finished
                    else service.delete_raw_material(product_id)
                )
                if not success:
                    return {"error": f"Produit {product_id} introuvable ou lie a des operations."}
                await session.commit()
            return {"success": True, "message": f"Produit {product_id} supprimé."}

    elif func_name == "search_products":
            q = func_args.get("query", "").strip()
            from app.core.perf_cache import async_cached_result
            async def builder():
                from sqlmodel import text
                async with session_maker() as session:
                    finished = (await session.execute(text(
                        "SELECT id, name, sale_price, avg_cost, default_unit, stock_qty FROM finished_products WHERE lower(name) LIKE :q LIMIT 50"
                    ), {"q": f"%{q.lower()}%"})).fetchall()
                    raw = (await session.execute(text(
                        "SELECT id, name, avg_cost, unit, stock_qty FROM raw_materials WHERE lower(name) LIKE :q LIMIT 50"
                    ), {"q": f"%{q.lower()}%"})).fetchall()
                results = []
                for r in finished:
                    results.append({"id": r[0], "name": r[1], "category": "finished", "sale_price": float(r[2] or 0), "avg_cost": float(r[3] or 0), "unit": r[4], "stock_qty": float(r[5] or 0)})
                for r in raw:
                    results.append({"id": r[0], "name": r[1], "category": "raw", "sale_price": 0.0, "avg_cost": float(r[2] or 0), "unit": r[3], "stock_qty": float(r[4] or 0)})
                return results
            res = await async_cached_result(("assistant", "search_products", q), builder, ttl_seconds=30.0)
            return {"results": res}

    elif func_name == "import_bulk_products_excel":
            filepath = func_args.get("filepath", "")
            is_raw = bool(func_args.get("is_raw_material", False))
            abs_path = os.path.abspath(filepath)
            workspace_dir = os.path.abspath(str(BASE_DIR))
            try:
                _assert_workspace_path(abs_path, workspace_dir)
            except ValueError as e:
                return {"error": str(e)}
    
            from app.services.excel_import_service import parse_excel_bulk_products
            try:
                parsed_products = parse_excel_bulk_products(abs_path)
            except Exception as e:
                return {"error": f"Erreur de lecture du fichier Excel : {str(e)}"}
    
            from app.modules.catalog.application.services import CatalogService
            from app.modules.catalog.api.schemas import RawMaterialCreateSchema, FinishedProductCreateSchema
    
            imported_count = 0
            async with session_maker() as session:
                service = CatalogService(session)
                for p_data in parsed_products:
                    try:
                        if is_raw:
                            schema = RawMaterialCreateSchema(
                                name=p_data["name"],
                                unit=p_data["unit"],
                                stock_qty=p_data["stock_qty"],
                                avg_cost=p_data["avg_cost"],
                                sale_price=p_data["sale_price"],
                                alert_threshold=p_data["alert_threshold"]
                            )
                            await service.create_raw_material(schema)
                        else:
                            schema = FinishedProductCreateSchema(
                                name=p_data["name"],
                                default_unit=p_data["unit"],
                                stock_qty=p_data["stock_qty"],
                                sale_price=p_data["sale_price"],
                                avg_cost=p_data["avg_cost"]
                            )
                            await service.create_finished_product(schema)
                        imported_count += 1
                    except Exception as e:
                        logger.warning("Échec d'importation du produit bulk %s : %s", p_data.get("name"), e)
                await session.commit()
    
            label = "matières premières" if is_raw else "produits finis"
            return {
                "success": True,
                "message": f"Importation en masse réussie : {imported_count}/{len(parsed_products)} {label} importés avec succès."
            }

    elif func_name == "get_enum_values":
            from app.modules.assistant.business_helpers import get_enum_values as bh_get_enum_values
            table = func_args.get("table", "").lower()
            column = func_args.get("column", "").lower()
            return bh_get_enum_values(table, column)

    return None
