from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.db_helpers import db_manager

logger = logging.getLogger("fabouanes.assistant")


def log_structured_failure(action: str, error: str, parameters: dict):
    from app.core.config import BASE_DIR
    import datetime
    import json
    log_file = BASE_DIR / "sabrina_failures.jsonl"
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "error": error,
        "parameters": parameters
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("Failed to write structured failure log: %s", e)


def log_sabrina_action(action: str, args: dict, confirmed: bool, success: bool, result_summary: str):
    from app.core.config import BASE_DIR
    import datetime
    import json
    log_file = BASE_DIR / "sabrina_audit.jsonl"
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "arguments": args,
        "confirmed": confirmed,
        "success": success,
        "result_summary": result_summary
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("Failed to write sabrina audit log: %s", e)


async def execute_tool_action(func_name: str, func_args: dict) -> Dict[str, Any]:
    from app.core.async_db import get_async_sessionmaker
    session_maker = get_async_sessionmaker()
    try:
        res = await _execute_tool_action_inner(func_name, func_args, session_maker)
        if isinstance(res, dict) and "error" in res:
            log_structured_failure(func_name, res["error"], func_args)
        else:
            summary = res.get("message") or res.get("print_url") or "Opération réussie"
            log_sabrina_action(func_name, func_args, confirmed=True, success=True, result_summary=str(summary))
        return res
    except Exception as e:
        logger.error("Error executing agent action %s with args %s: %s", func_name, func_args, e, exc_info=True)
        log_structured_failure(func_name, str(e), func_args)
        return {"error": str(e)}


def sanitize_numeric(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Retirer les suffixes de devise ou d'unité courants
    for suffix in ("da", "dzd", "da.", "dzd.", "kg", "sac", "q", "u", "€", "$"):
        if s.lower().endswith(suffix):
            s = s[:-len(suffix)].strip()
    s = s.replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


async def search_web(query: str) -> Dict[str, Any]:
    from app.core.perf_cache import async_cached_result
    async def builder():
        import httpx
        import urllib.parse
        import re
        import html
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=12.0)
                if res.status_code != 200:
                    return {"error": f"DuckDuckGo a renvoyé le statut HTTP {res.status_code}"}

                parts = res.text.split('<div class="result results_links results_links_deep web-result ')
                results = []

                for block in parts[1:7]:  # Limiter aux 6 premiers résultats
                    title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                    snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</', block, re.DOTALL)

                    if title_match:
                        raw_url = title_match.group(1)
                        raw_title = title_match.group(2)

                        url_clean = raw_url
                        if "uddg=" in raw_url:
                            try:
                                parsed = urllib.parse.urlparse(raw_url)
                                queries = urllib.parse.parse_qs(parsed.query)
                                if "uddg" in queries:
                                    url_clean = queries["uddg"][0]
                            except Exception:
                                pass
                        elif url_clean.startswith("//"):
                            url_clean = "https:" + url_clean

                        title = re.sub(r'<[^>]*>', '', raw_title)
                        title = html.unescape(title).strip()

                        snippet = ""
                        if snippet_match:
                            raw_snippet = snippet_match.group(1)
                            snippet = re.sub(r'<[^>]*>', '', raw_snippet)
                            snippet = html.unescape(snippet).strip()

                        results.append({
                            "title": title,
                            "url": url_clean,
                            "snippet": snippet
                        })
                return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    return await async_cached_result(("assistant", "search_web", query), builder, ttl_seconds=300.0)


async def _execute_tool_action_inner(func_name: str, func_args: dict, session_maker) -> Dict[str, Any]:
    from app.core.config import BASE_DIR
    import os

    if func_name == "read_app_file":
        filepath = func_args.get("filepath", "")
        workspace_dir = os.path.abspath(str(BASE_DIR))
        abs_path = os.path.abspath(filepath)
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}
        with open(abs_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}

    elif func_name == "modify_app_file":
        filepath = func_args.get("filepath", "")
        old_c = func_args.get("old_content", "")
        new_c = func_args.get("new_content", "")
        workspace_dir = os.path.abspath(str(BASE_DIR))
        abs_path = os.path.abspath(filepath)
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_c not in content:
            return {"error": "Le contenu original à remplacer n'a pas été trouvé dans le fichier."}
        new_content = content.replace(old_c, new_c, 1)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"success": True, "message": "Fichier modifié avec succès."}

    elif func_name == "list_user_notes":
        from app.utils.tool_pages import list_user_notes
        return {"notes": list_user_notes()}

    elif func_name == "get_user_note":
        from app.utils.tool_pages import get_user_note
        note_id = func_args.get("note_id", "")
        return {"note": get_user_note(note_id)}

    elif func_name == "create_user_note":
        from app.utils.tool_pages import create_user_note
        title = func_args.get("title", "Sans titre")
        content = func_args.get("content", "")
        color = func_args.get("color", "yellow")
        return {"note": create_user_note(title, content, color)}

    elif func_name == "save_user_note":
        from app.utils.tool_pages import save_user_note
        note_id = func_args.get("note_id", "")
        title = func_args.get("title", "")
        content = func_args.get("content", "")
        color = func_args.get("color", "yellow")
        pinned = bool(func_args.get("pinned", False))
        return {"note": save_user_note(note_id, title, content, color, pinned)}

    elif func_name == "delete_user_note":
        from app.utils.tool_pages import delete_user_note
        note_id = func_args.get("note_id", "")
        return {"success": delete_user_note(note_id)}

    elif func_name == "create_app_backup":
        from app.services.admin_service import create_manual_backup
        res = await create_manual_backup()
        return {"success": True, "backup": res}

    elif func_name == "list_app_backups":
        from app.services.admin_service import list_restore_backups
        res = list_restore_backups()
        return {"backups": res}

    elif func_name == "restore_app_backup":
        backup_name = func_args.get("backup_name", "")
        from app.services.admin_service import restore_backup_by_value
        await restore_backup_by_value(backup_name)
        return {"success": True, "message": "Restauration effectuée avec succès."}

    elif func_name == "create_app_user":
        username = func_args.get("username", "")
        password = func_args.get("password", "")
        role = func_args.get("role", "operator")
        from app.services.admin_service import create_user_account
        res = await create_user_account(username, password, role)
        if not res.get("ok"):
            return {"error": res.get("message", "Creation utilisateur refusee.")}
        return {"success": True, "message": res.get("message", f"Utilisateur {username} cree.")}

    elif func_name == "change_app_user_password":
        username = func_args.get("username", "")
        new_password = func_args.get("new_password", "")
        from app.core.security import validate_password_strength
        from app.services.auth_service import get_user_by_username, generate_password_hash
        from app.modules.users.repository import update_password
        ok, password_msg = validate_password_strength(new_password)
        if not ok:
            return {"error": password_msg}
        user = await get_user_by_username(username)
        if not user:
            return {"error": f"Utilisateur {username} introuvable."}
        async with session_maker() as session:
            await update_password(user["id"], generate_password_hash(new_password), 0, db=session)
            await session.commit()
        return {"success": True, "message": f"Mot de passe de {username} modifié."}

    elif func_name == "delete_app_user":
        username = func_args.get("username", "")
        from app.services.auth_service import get_user_by_username
        user = await get_user_by_username(username)
        if not user:
            return {"error": f"Utilisateur {username} introuvable."}
        async with session_maker() as session:
            from sqlmodel import text
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user["id"]})
            await session.commit()
        return {"success": True, "message": f"Utilisateur {username} supprimé."}

    elif func_name == "update_setting":
        key = func_args.get("key", "")
        value = func_args.get("value", "")
        db_manager.set_setting(key, value)
        return {"success": True, "message": f"Paramètre {key} mis à jour."}

    elif func_name == "add_client":
        name = str(func_args.get("name", "")).strip().title()
        phone = "".join(c for c in str(func_args.get("phone", "")) if c.isdigit())
        address = str(func_args.get("address", "")).strip()
        notes = str(func_args.get("notes", "")).strip()
        opening_credit = sanitize_numeric(func_args.get("opening_credit"))
        from app.modules.clients.service import ClientService
        from app.modules.clients.schemas_validation import ClientCreateSchema
        schema = ClientCreateSchema(name=name, phone=phone, address=address, notes=notes, opening_credit=opening_credit)
        async with session_maker() as session:
            service = ClientService(session)
            client = await service.create_client(schema)
            await session.commit()
        return {"success": True, "client_id": client.id}

    elif func_name == "modify_client":
        client_id = int(func_args.get("client_id"))
        name = func_args.get("name")
        if name:
            name = str(name).strip().title()
        phone = func_args.get("phone")
        if phone:
            phone = "".join(c for c in str(phone) if c.isdigit())
        address = func_args.get("address")
        if address:
            address = str(address).strip()
        notes = func_args.get("notes")
        if notes:
            notes = str(notes).strip()
        from app.modules.clients.service import ClientService
        from app.modules.clients.schemas_validation import ClientUpdateSchema
        async with session_maker() as session:
            service = ClientService(session)
            if not name:
                existing = await service.get_client(client_id)
                if existing:
                    name = existing.name
            schema = ClientUpdateSchema(name=name, phone=phone, address=address, notes=notes)
            await service.update_client(client_id, schema)
            await session.commit()
        return {"success": True, "message": f"Client {client_id} modifié."}

    elif func_name == "delete_client":
        client_id = int(func_args.get("client_id"))
        from app.modules.clients.service import ClientService
        async with session_maker() as session:
            service = ClientService(session)
            await service.delete_client(client_id)
            await session.commit()
        return {"success": True, "message": f"Client {client_id} supprimé."}

    elif func_name == "add_supplier":
        name = str(func_args.get("name", "")).strip().title()
        phone = str(func_args.get("phone", "")).strip()
        address = str(func_args.get("address", "")).strip()
        notes = str(func_args.get("notes", "")).strip()
        from app.core.schema.supplier_validation import SupplierValidationSchema
        from app.services.contact_directory_service import create_supplier_from_form
        schema = SupplierValidationSchema(name=name, phone=phone, address=address, notes=notes)
        async with session_maker() as session:
            supplier_id = await create_supplier_from_form(schema.model_dump(), db=session)
            await session.commit()
        return {"success": True, "supplier_id": supplier_id}

    elif func_name == "modify_supplier":
        supplier_id = int(func_args.get("supplier_id"))
        from app.core.schema.supplier_validation import SupplierValidationSchema
        from app.services.contact_directory_service import get_supplier, update_supplier_from_form
        async with session_maker() as session:
            existing = await get_supplier(supplier_id, db=session)
            if not existing:
                return {"error": f"Fournisseur {supplier_id} introuvable."}
            data = {
                "name": str(func_args.get("name", existing.get("name", ""))).strip().title(),
                "phone": str(func_args.get("phone", existing.get("phone") or "")).strip(),
                "address": str(func_args.get("address", existing.get("address") or "")).strip(),
                "notes": str(func_args.get("notes", existing.get("notes") or "")).strip(),
            }
            schema = SupplierValidationSchema(**data)
            await update_supplier_from_form(supplier_id, schema.model_dump(), db=session)
            await session.commit()
        return {"success": True, "message": f"Fournisseur {supplier_id} modifie."}

    elif func_name == "delete_supplier":
        supplier_id = int(func_args.get("supplier_id"))
        from sqlalchemy import func
        from sqlmodel import select
        from app.core.models import Purchase, PurchaseDocument
        from app.services.contact_directory_service import delete_supplier_by_id, get_supplier
        async with session_maker() as session:
            existing = await get_supplier(supplier_id, db=session)
            if not existing:
                return {"error": f"Fournisseur {supplier_id} introuvable."}
            purchases_count = (
                await session.execute(select(func.count()).select_from(Purchase).where(Purchase.supplier_id == supplier_id))
            ).scalar() or 0
            docs_count = (
                await session.execute(select(func.count()).select_from(PurchaseDocument).where(PurchaseDocument.supplier_id == supplier_id))
            ).scalar() or 0
            if purchases_count or docs_count:
                return {"error": f"Fournisseur {supplier_id} lie a des achats; suppression refusee."}
            await delete_supplier_by_id(supplier_id, db=session)
            await session.commit()
        return {"success": True, "message": f"Fournisseur {supplier_id} supprime."}

    elif func_name == "add_product":
        name = str(func_args.get("name", "")).strip().title()
        category = str(func_args.get("category", "")).strip().lower()
        price = sanitize_numeric(func_args.get("price"))
        cost = sanitize_numeric(func_args.get("cost"))
        unit = str(func_args.get("unit", "kg")).strip().lower()
        stock_qty = sanitize_numeric(func_args.get("stock_qty", 0.0))
        alert_threshold = sanitize_numeric(func_args.get("alert_threshold", 0.0))
        is_finished = category in ("finished", "produit final", "produit")
        from app.modules.catalog.service import CatalogService
        from app.modules.catalog.schemas_validation import FinishedProductCreateSchema, RawMaterialCreateSchema
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
        from app.modules.catalog.service import CatalogService
        from app.modules.catalog.schemas_validation import FinishedProductUpdateSchema, RawMaterialUpdateSchema
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
        from app.modules.catalog.service import CatalogService
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

    elif func_name == "add_sale":
        client_id = func_args.get("client_id")
        if client_id:
            client_id = int(client_id)
        item_kind = str(func_args.get("item_kind", "finished")).strip().lower()
        item_id = func_args.get("item_id") or func_args.get("finished_product_id")
        if item_id is None:
            return {"error": "Paramètre finished_product_id ou item_id requis."}
        item_id = int(item_id)
        quantity = sanitize_numeric(func_args.get("quantity"))
        unit = str(func_args.get("unit", "kg")).strip().lower()
        unit_price = sanitize_numeric(func_args.get("unit_price"))
        amount_paid = sanitize_numeric(func_args.get("amount_paid", 0.0))
        notes = str(func_args.get("notes", "")).strip()
        from app.modules.sales.service import SalesService
        from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema
        line = SaleLineSchema(item_key=f"{item_kind}:{item_id}", quantity=quantity, unit=unit, unit_price=unit_price)
        schema = SaleFormSchema(client_id=client_id, notes=notes, lines=[line])
        async with session_maker() as session:
            service = SalesService(session)
            res = await service.create_sale_from_form(schema)
            if amount_paid > 0 and client_id:
                from app.modules.payments.service import PaymentsService
                from app.modules.payments.schemas_validation import PaymentFormSchema
                pay_service = PaymentsService(session)
                pay_schema = PaymentFormSchema(client_id=client_id, amount=amount_paid, payment_type="versement", notes=f"Paiement partiel vente {res.get('sale_id') or res.get('document_id')}")
                await pay_service.create_payment_from_form(pay_schema)
            await session.commit()
        return {"success": True, "sale_id": res.get("sale_id") or res.get("document_id") or res.get("print_item_id")}

    elif func_name == "add_purchase":
        supplier_id = func_args.get("supplier_id")
        if supplier_id:
            supplier_id = int(supplier_id)
        item_kind = str(func_args.get("item_kind", "raw")).strip().lower()
        item_id = func_args.get("item_id") or func_args.get("raw_material_id")
        if item_id is None:
            return {"error": "Paramètre raw_material_id ou item_id requis."}
        item_id = int(item_id)
        quantity = sanitize_numeric(func_args.get("quantity"))
        unit = str(func_args.get("unit", "kg")).strip().lower()
        unit_price = sanitize_numeric(func_args.get("unit_price"))
        notes = str(func_args.get("notes", "")).strip()
        from app.modules.purchases.service import PurchaseService
        from app.modules.purchases.schemas_validation import PurchaseFormSchema, PurchaseLineSchema
        line = PurchaseLineSchema(raw_material_id=f"{item_kind}:{item_id}", quantity=quantity, unit=unit, unit_price=unit_price)
        schema = PurchaseFormSchema(supplier_id=supplier_id, notes=notes, lines=[line])
        async with session_maker() as session:
            service = PurchaseService(session)
            res = await service.create_purchase_from_form(schema)
            await session.commit()
        return {"success": True, "purchase_id": res.get("purchase_id") or res.get("document_id")}

    elif func_name == "add_payment":
        client_id = int(func_args.get("client_id"))
        amount = sanitize_numeric(func_args.get("amount"))
        payment_type = str(func_args.get("payment_type", "versement")).strip().lower()
        # Ensure it is exactly one of the accepted payments enums: versement or avance
        if payment_type not in ("versement", "avance"):
            payment_type = "versement"
        notes = str(func_args.get("notes", "")).strip()
        from app.modules.payments.service import PaymentsService
        from app.modules.payments.schemas_validation import PaymentFormSchema
        schema = PaymentFormSchema(client_id=client_id, amount=amount, payment_type=payment_type, notes=notes)
        async with session_maker() as session:
            service = PaymentsService(session)
            res = await service.create_payment_from_form(schema)
            await session.commit()
        return {"success": True, "payment_id": res[0]}

    elif func_name == "delete_operation":
        tx_kind = func_args.get("tx_kind")
        tx_id = int(func_args.get("tx_id"))
        async with session_maker() as session:
            if tx_kind in ("sale_finished", "sale_raw", "sale"):
                from app.modules.sales.service import SalesService
                service = SalesService(session)
                await service.delete_sale_by_id(tx_id)
            elif tx_kind == "purchase":
                from app.modules.purchases.service import PurchaseService
                service = PurchaseService(session)
                await service.delete_purchase_by_id(tx_id)
            elif tx_kind == "payment":
                from app.modules.payments.service import PaymentsService
                service = PaymentsService(session)
                await service.delete_payment_by_id(tx_id)
            await session.commit()
        return {"success": True, "message": f"Opération {tx_kind} {tx_id} supprimée."}

    elif func_name == "add_expense":
        category = str(func_args.get("category", "")).strip().lower()
        amount = sanitize_numeric(func_args.get("amount"))
        description = str(func_args.get("description", "")).strip()
        payment_method = str(func_args.get("payment_method", "cash")).strip().lower()

        # Normalize category
        cat_map = {
            "matiere_premiere": "general", "matière première": "general", "matière": "general",
            "carburant": "transport", "essence": "transport", "gazole": "transport", "transport": "transport",
            "fournitures": "fournitures", "fournitures de bureau": "fournitures",
            "loyer": "loyer",
            "salaires": "salaires", "salaire": "salaires", "paie": "salaires",
            "maintenance": "maintenance", "reparation": "maintenance", "réparation": "maintenance",
            "telecom": "telecom", "internet": "telecom", "telephone": "telecom", "téléphone": "telecom",
            "energie": "energie", "électricité": "energie", "electricite": "energie", "eau": "energie", "gaz": "energie",
            "impots": "impots", "impôt": "impots", "taxe": "impots", "taxes": "impots",
            "autre": "autre", "divers": "autre"
        }
        allowed_literals = {"general", "transport", "fournitures", "loyer", "salaires", "maintenance", "telecom", "energie", "impots", "autre"}
        if category in cat_map:
            category = cat_map[category]
        elif category not in allowed_literals:
            # Leave it as is so ExpenseCreateSchema validation fails naturally
            pass

        # Normalize payment method
        method_map = {
            "espèces": "cash", "espèce": "cash", "especes": "cash", "espece": "cash", "cash": "cash",
            "chèque": "cheque", "cheque": "cheque",
            "virement": "virement", "ccp": "virement",
            "autre": "autre"
        }
        payment_method = method_map.get(payment_method, "cash")

        from app.modules.expenses.schemas_validation import ExpenseCreateSchema
        import datetime
        schema = ExpenseCreateSchema(
            date=datetime.date.today(),
            category=category,
            description=description,
            amount=amount,
            payment_method=payment_method
        )
        from app.modules.expenses.service import add_expense
        async with session_maker() as session:
            expense_id = await add_expense(
                db=session,
                date=schema.date.isoformat(),
                category=schema.category,
                description=schema.description,
                amount=schema.amount,
                method=schema.payment_method
            )
            await session.commit()
        return {"success": True, "message": "Dépense enregistrée.", "expense_id": expense_id}

    elif func_name == "modify_expense":
        expense_id = int(func_args.get("expense_id"))
        category = func_args.get("category")
        if category:
            category = str(category).strip().lower()
            cat_map = {
                "matiere_premiere": "general", "matière première": "general", "matière": "general",
                "carburant": "transport", "essence": "transport", "gazole": "transport", "transport": "transport",
                "fournitures": "fournitures", "fournitures de bureau": "fournitures",
                "loyer": "loyer",
                "salaires": "salaires", "salaire": "salaires", "paie": "salaires",
                "maintenance": "maintenance", "reparation": "maintenance", "réparation": "maintenance",
                "telecom": "telecom", "internet": "telecom", "telephone": "telecom", "téléphone": "telecom",
                "energie": "energie", "électricité": "energie", "electricite": "energie", "eau": "energie", "gaz": "energie",
                "impots": "impots", "impôt": "impots", "taxe": "impots", "taxes": "impots",
                "autre": "autre", "divers": "autre"
            }
            category = cat_map.get(category, "autre")
        amount = func_args.get("amount")
        if amount is not None:
            amount = sanitize_numeric(amount)
        description = func_args.get("description")
        if description:
            description = str(description).strip()
        from app.modules.expenses.service import get_expense, modify_expense
        async with session_maker() as session:
            db_exp = await get_expense(session, expense_id)
            if not db_exp:
                return {"error": f"Dépense ID {expense_id} introuvable."}
            new_date = db_exp.date
            new_category = category if category is not None else db_exp.category
            new_amount = amount if amount is not None else float(db_exp.amount)
            new_description = description if description is not None else db_exp.description
            new_method = db_exp.payment_method
            await modify_expense(
                db=session,
                expense_id=expense_id,
                date=new_date,
                category=new_category,
                description=new_description,
                amount=new_amount,
                method=new_method
            )
            await session.commit()
        return {"success": True, "message": f"Dépense {expense_id} modifiée."}

    elif func_name == "delete_expense":
        expense_id = int(func_args.get("expense_id"))
        from app.modules.expenses.service import remove_expense
        async with session_maker() as session:
            await remove_expense(db=session, expense_id=expense_id)
            await session.commit()
        return {"success": True, "message": f"Dépense {expense_id} supprimée."}

    elif func_name == "add_production_batch":
        finished_product_id = int(func_args.get("finished_product_id"))
        quantity = sanitize_numeric(func_args.get("quantity"))
        notes = str(func_args.get("notes", "")).strip()

        from app.core.models_pkg.catalog import FinishedProduct, RawMaterial
        from app.core.models_pkg.production import ProductionBatch, ProductionBatchItem, SavedRecipe, SavedRecipeItem
        from app.services.stock_service import apply_finished_production, apply_raw_material_consumption
        from sqlmodel import select
        from decimal import Decimal
        import datetime

        async with session_maker() as session:
            # 1. Fetch finished product
            prod_res = await session.execute(select(FinishedProduct).where(FinishedProduct.id == finished_product_id))
            db_product = prod_res.scalar_one_or_none()
            if not db_product:
                return {"error": f"Produit final ID {finished_product_id} introuvable."}

            # 2. Check for a recipe
            recipe_res = await session.execute(select(SavedRecipe).where(SavedRecipe.finished_product_id == finished_product_id))
            db_recipe = recipe_res.scalar_one_or_none()

            recipe_lines = []
            total_cost = 0.0

            if db_recipe:
                # Fetch recipe ingredients
                items_res = await session.execute(select(SavedRecipeItem).where(SavedRecipeItem.recipe_id == db_recipe.id))
                recipe_items = items_res.scalars().all()

                for item in recipe_items:
                    mat_res = await session.execute(select(RawMaterial).where(RawMaterial.id == item.raw_material_id))
                    material = mat_res.scalar_one_or_none()
                    if not material:
                        return {"error": f"Matière première ID {item.raw_material_id} introuvable dans la recette."}

                    req_qty = float(item.quantity) * quantity
                    line_cost = req_qty * float(material.avg_cost)
                    recipe_lines.append({
                        "material": material,
                        "qty": req_qty,
                        "unit_cost": float(material.avg_cost),
                        "line_cost": line_cost
                    })
                    total_cost += line_cost

            # 3. Create the batch
            batch = ProductionBatch(
                finished_product_id=finished_product_id,
                output_quantity=Decimal(str(quantity)),
                production_cost=Decimal(str(total_cost)),
                unit_cost=Decimal(str(total_cost / quantity if quantity > 0 else 0.0)),
                production_date=datetime.date.today(),
                notes=notes
            )
            session.add(batch)
            await session.flush()
            batch_id = batch.id

            # 4. Consume ingredients and add batch items
            for line in recipe_lines:
                item = ProductionBatchItem(
                    batch_id=batch_id,
                    raw_material_id=line["material"].id,
                    quantity=Decimal(str(line["qty"])),
                    unit_cost_snapshot=Decimal(str(line["unit_cost"])),
                    line_cost=Decimal(str(line["line_cost"]))
                )
                session.add(item)
                # Deduct from raw material stock and record movement
                await apply_raw_material_consumption(
                    material={"id": line["material"].id},
                    qty=line["qty"],
                    reference_type="production",
                    reference_id=batch_id,
                    reason="production",
                    db=session
                )

            # 5. Add finished product to stock and record movement
            await apply_finished_production(
                product={"id": finished_product_id},
                output_qty=quantity,
                total_cost=total_cost,
                reference_id=batch_id,
                db=session
            )

            await session.commit()

        return {"success": True, "batch_id": batch_id}

    elif func_name == "delete_production":
        batch_id = int(func_args.get("batch_id"))
        from app.services.production_service import delete_production_by_id
        async with session_maker() as session:
            await delete_production_by_id(batch_id, db=session)
            await session.commit()
        return {"success": True, "message": f"Production {batch_id} supprimée."}

    elif func_name == "redirect_to":
        url = func_args.get("url", "/")
        return {"redirect_url": url}

    elif func_name == "change_theme":
        theme = func_args.get("theme", "light")
        return {"theme": theme}

    elif func_name == "get_enum_values":
        from app.modules.assistant.business_helpers import get_enum_values as bh_get_enum_values
        table = func_args.get("table", "").lower()
        column = func_args.get("column", "").lower()
        return bh_get_enum_values(table, column)

    elif func_name == "search_clients":
        q = func_args.get("query", "").strip()
        from app.core.perf_cache import async_cached_result
        async def builder():
            from sqlmodel import text
            async with session_maker() as session:
                rows = (await session.execute(text(
                    """SELECT id, name, phone,
                              COALESCE((SELECT SUM(balance_due) FROM sales WHERE client_id = c.id), 0) AS debt
                       FROM clients c WHERE lower(name) LIKE :q LIMIT 50"""
                ), {"q": f"%{q.lower()}%"})).fetchall()
            return [{"id": r[0], "name": r[1], "phone": r[2], "debt": float(r[3] or 0)} for r in rows]
        res = await async_cached_result(("assistant", "search_clients", q), builder, ttl_seconds=30.0)
        return {"results": res}

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

    elif func_name == "add_supplier_payment":
        supplier_id = int(func_args.get("supplier_id"))
        amount = sanitize_numeric(func_args.get("amount"))
        payment_type = str(func_args.get("payment_type", "versement")).strip().lower()
        if payment_type not in ("versement", "avance"):
            payment_type = "versement"
        notes = str(func_args.get("notes", "")).strip()
        purchase_id = func_args.get("purchase_id")
        if purchase_id:
            purchase_id = int(purchase_id)
        import datetime
        from sqlmodel import text
        async with session_maker() as session:
            # Verify supplier exists
            supplier_exists = (await session.execute(
                text("SELECT id FROM suppliers WHERE id = :sid"), {"sid": supplier_id}
            )).fetchone()
            if not supplier_exists:
                return {"error": f"Fournisseur ID {supplier_id} introuvable."}
            if amount <= 0:
                return {"error": "Le montant du versement doit être supérieur à 0."}
            result = await session.execute(
                text("""
                    INSERT INTO supplier_payments (supplier_id, purchase_id, payment_type, amount, payment_date, notes)
                    VALUES (:sid, :pid, :ptype, :amount, :pdate, :notes)
                    RETURNING id
                """),
                {
                    "sid": supplier_id,
                    "pid": purchase_id,
                    "ptype": payment_type,
                    "amount": amount,
                    "pdate": datetime.date.today().isoformat(),
                    "notes": notes,
                }
            )
            payment_row = result.fetchone()
            await session.commit()
        payment_id = payment_row[0] if payment_row else None
        return {
            "success": True,
            "payment_id": payment_id,
            "message": f"Versement fournisseur de {amount:.2f} DA enregistré (ID: {payment_id})."
        }

    elif func_name == "get_business_insights":
        insight_type = func_args.get("insight_type", "summary").lower()
        from app.core.perf_cache import async_cached_result
        async def builder():
            from sqlmodel import text
            async with session_maker() as session:
                if insight_type == "top_debtors":
                    rows = (await session.execute(text(
                        "SELECT name, phone, current_balance FROM clients_with_stats WHERE current_balance > 0 ORDER BY current_balance DESC LIMIT 5"
                    ))).fetchall()
                    return {"top_debtors": [{"name": r[0], "phone": r[1], "debt": float(r[2])} for r in rows]}
                elif insight_type == "monthly_sales_comparison":
                    sales_cur = (await session.execute(text(
                        "SELECT COALESCE(SUM(total), 0) FROM sale_documents WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE)"
                    ))).scalar()
                    sales_prev = (await session.execute(text(
                        "SELECT COALESCE(SUM(total), 0) FROM sale_documents WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND sale_date < DATE_TRUNC('month', CURRENT_DATE)"
                    ))).scalar()
                    sales_cur = float(sales_cur)
                    sales_prev = float(sales_prev)
                    growth = ((sales_cur - sales_prev) / sales_prev * 100) if sales_prev > 0 else 0.0
                    return {
                        "sales_current_month": sales_cur,
                        "sales_previous_month": sales_prev,
                        "growth_rate": round(growth, 2)
                    }
                else:
                    clients_count = (await session.execute(text("SELECT COUNT(*) FROM clients"))).scalar()
                    products_count = (await session.execute(text("SELECT COUNT(*) FROM finished_products"))).scalar()
                    sales_month = (await session.execute(text("SELECT COALESCE(SUM(total), 0) FROM sale_documents WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE)"))).scalar()
                    return {
                        "total_clients": clients_count,
                        "total_products": products_count,
                        "sales_this_month": float(sales_month)
                    }
        res = await async_cached_result(("assistant", "get_business_insights", insight_type), builder, ttl_seconds=60.0)
        return res

    elif func_name == "get_print_link":
        dt = func_args.get("doc_type", "").lower()
        item_id = int(func_args.get("item_id"))
        allowed = {
            "sale_finished": f"/print/sale_finished/{item_id}",
            "sale_raw": f"/print/sale_raw/{item_id}",
            "purchase": f"/print/purchase/{item_id}",
            "payment": f"/print/payment/{item_id}",
            "production": f"/print/production/{item_id}",
            "client_history": f"/contacts/clients/{item_id}/print-history"
        }
        url = allowed.get(dt)
        if url:
            return {
                "print_url": url,
                "pdf_url": f"{url}?format=pdf",
                "message": f"Voici les liens d'impression :\n- [Imprimer/Voir]({url})\n- [Télécharger en PDF]({url}?format=pdf)"
            }
        return {"error": f"Type de document '{dt}' non supporté pour l'impression."}

    elif func_name == "import_client_excel":
        filepath = func_args.get("filepath", "")
        abs_path = os.path.abspath(filepath)
        workspace_dir = os.path.abspath(str(BASE_DIR))
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}
        from app.services.excel_import_service import parse_excel_client_file
        try:
            data = parse_excel_client_file(abs_path)
        except Exception as e:
            return {"error": f"Erreur de lecture du fichier Excel : {str(e)}"}
        from app.modules.clients.service import ClientService
        from app.modules.clients.schemas_validation import ClientCreateSchema
        schema = ClientCreateSchema(
            name=data["name"],
            phone=data["phone"],
            address=data["address"],
            notes=data["notes"],
            opening_credit=data["opening_credit"]
        )
        async with session_maker() as session:
            service = ClientService(session)
            client = await service.create_client(schema)
            await session.commit()
        return {
            "success": True,
            "client_id": client.id,
            "message": f"Client '{data['name']}' importé avec succès avec un solde initial de {data['opening_credit']} DA (Lignes détectées : {data['history_count']})."
        }

    elif func_name == "import_client_history_excel":
        filepath = func_args.get("filepath", "")
        client_id_val = func_args.get("client_id")
        client_id = int(client_id_val) if client_id_val is not None else None

        abs_path = os.path.abspath(filepath)
        workspace_dir = os.path.abspath(str(BASE_DIR))
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}

        from app.modules.clients.service import ClientService
        async with session_maker() as session:
            service = ClientService(session)
            try:
                res = await service.import_client_history_from_excel(abs_path, client_id=client_id, force_reimport=True)
                await session.commit()
                return {
                    "success": True,
                    "message": f"Historique Excel importé avec succès pour le client '{res.get('client_name')}' (Nombre de lignes : {res.get('nb_lignes')}, solde final : {res.get('solde_final')} DA)."
                }
            except Exception as e:
                return {"error": f"Erreur lors de l'import de l'historique : {str(e)}"}

    elif func_name == "import_bulk_clients_excel":
        filepath = func_args.get("filepath", "")
        abs_path = os.path.abspath(filepath)
        workspace_dir = os.path.abspath(str(BASE_DIR))
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}

        from app.services.excel_import_service import parse_excel_bulk_clients
        try:
            parsed_clients = parse_excel_bulk_clients(abs_path)
        except Exception as e:
            return {"error": f"Erreur de lecture du fichier Excel : {str(e)}"}

        from app.modules.clients.service import ClientService
        from app.modules.clients.schemas_validation import ClientCreateSchema

        imported_count = 0
        async with session_maker() as session:
            service = ClientService(session)
            for c_data in parsed_clients:
                try:
                    schema = ClientCreateSchema(
                        name=c_data["name"],
                        phone=c_data["phone"],
                        address=c_data["address"],
                        notes=c_data["notes"],
                        opening_credit=c_data["opening_credit"]
                    )
                    await service.create_client(schema)
                    imported_count += 1
                except Exception as e:
                    logger.warning("Échec d'importation du client bulk %s : %s", c_data.get("name"), e)
            await session.commit()

        return {
            "success": True,
            "message": f"Importation en masse réussie : {imported_count}/{len(parsed_clients)} clients importés avec succès."
        }

    elif func_name == "import_bulk_products_excel":
        filepath = func_args.get("filepath", "")
        is_raw = bool(func_args.get("is_raw_material", False))
        abs_path = os.path.abspath(filepath)
        workspace_dir = os.path.abspath(str(BASE_DIR))
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}

        from app.services.excel_import_service import parse_excel_bulk_products
        try:
            parsed_products = parse_excel_bulk_products(abs_path)
        except Exception as e:
            return {"error": f"Erreur de lecture du fichier Excel : {str(e)}"}

        from app.modules.catalog.service import CatalogService
        from app.modules.catalog.schemas_validation import RawMaterialCreateSchema, FinishedProductCreateSchema

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

    elif func_name == "get_current_weather":
        location = func_args.get("location", "Paris").strip()
        from app.core.perf_cache import async_cached_result
        async def builder():
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(f"https://wttr.in/{location}?format=3", timeout=15.0)
                    if res.status_code == 200:
                        return {"weather": res.text.strip()}
                    return {"error": f"Code HTTP {res.status_code} retourné par le service météo."}
            except Exception as e:
                return {"error": str(e)}
        res = await async_cached_result(("assistant", "get_current_weather", location), builder, ttl_seconds=600.0)
        return res

    elif func_name == "search_web":
        query = func_args.get("query", "").strip()
        return await search_web(query)

    elif func_name == "remember":
        from app.modules.assistant.memory import remember as mem_remember
        content = func_args.get("content", "").strip()
        category = func_args.get("category", "general").strip()
        return mem_remember(content, category=category, source="user_explicit")

    elif func_name == "recall":
        from app.modules.assistant.memory import recall as mem_recall
        query = func_args.get("query", "").strip()
        return mem_recall(query, limit=10)

    elif func_name == "forget":
        from app.modules.assistant.memory import forget as mem_forget
        memory_id = func_args.get("memory_id", 0)
        return mem_forget(int(memory_id))

    elif func_name == "list_recipes":
        from app.services.recipe_service import load_saved_recipes
        recipes = await load_saved_recipes()
        return {"recipes": recipes}

    elif func_name == "create_recipe":
        from app.services.recipe_service import save_recipe_definition
        finished_id = int(func_args.get("finished_product_id") or 0)
        name = func_args.get("name", "").strip()
        notes = func_args.get("notes", "").strip()
        items = func_args.get("items", [])
        
        recipe_lines = []
        for it in items:
            raw_id = int(it.get("raw_material_id") or 0)
            qty = float(it.get("quantity") or 0.0)
            recipe_lines.append({
                "material": {"id": raw_id},
                "qty": qty
            })
            
        recipe_id = await save_recipe_definition(
            finished_id=finished_id,
            recipe_name=name,
            notes=notes,
            recipe_lines=recipe_lines
        )
        if recipe_id:
            return {"success": True, "recipe_id": recipe_id, "message": f"Recette '{name}' enregistrée avec succès (ID: {recipe_id})."}
        return {"error": "Impossible d'enregistrer la recette. Vérifiez les composants."}

    elif func_name == "delete_recipe":
        from sqlalchemy import delete
        from app.core.models import SavedRecipe, SavedRecipeItem
        recipe_id = int(func_args.get("recipe_id") or 0)
        async with session_maker() as session:
            async with session.begin():
                await session.execute(delete(SavedRecipeItem).where(SavedRecipeItem.recipe_id == recipe_id))
                await session.execute(delete(SavedRecipe).where(SavedRecipe.id == recipe_id))
        return {"success": True, "message": f"Recette #{recipe_id} supprimée avec succès."}

    elif func_name == "list_bon_space_documents":
        from app.services.bon_space_service import list_bon_space_documents
        q = func_args.get("query", "").strip()
        kind = func_args.get("kind", "").strip()
        limit = int(func_args.get("limit") or 80)
        docs = await list_bon_space_documents(q=q, kind=kind, limit=limit)
        for d in docs:
            d.pop("search_text", None)
        return {"documents": docs}

    elif func_name == "get_recent_activity_logs":
        from app.services.activity_service import list_admin_activity
        limit = int(func_args.get("limit") or 50)
        activities = await list_admin_activity(limit=limit)
        return {"logs": [act.get("sentence") for act in activities if act.get("sentence")]}

    elif func_name == "get_active_alerts":
        from sqlalchemy import select
        from app.core.models import RawMaterial, FinishedProduct
        from app.services.alert_service import check_overdue_clients
        
        alerts = []
        async with session_maker() as session:
            raws_res = await session.execute(
                select(RawMaterial.name, RawMaterial.stock_qty, RawMaterial.alert_threshold, RawMaterial.unit)
                .where(RawMaterial.stock_qty <= RawMaterial.alert_threshold, RawMaterial.alert_threshold > 0)
            )
            for row in raws_res.all():
                alerts.append(f"Alerte Stock Matière : '{row.name}' est bas ({row.stock_qty} {row.unit} restant, seuil: {row.alert_threshold})")
                
            finished_res = await session.execute(
                select(FinishedProduct.name, FinishedProduct.stock_qty, FinishedProduct.alert_threshold, FinishedProduct.unit)
                .where(FinishedProduct.stock_qty <= FinishedProduct.alert_threshold, FinishedProduct.alert_threshold > 0)
            )
            for row in finished_res.all():
                alerts.append(f"Alerte Stock Produit : '{row.name}' est bas ({row.stock_qty} {row.unit} restant, seuil: {row.alert_threshold})")
                
            overdue_clients = await check_overdue_clients(db=session)
            for cl in overdue_clients:
                alerts.append(f"Alerte Paiement : Client '{cl['name']}' est inactif depuis {int(cl['jours_inactif'] or 0)} jours avec une dette en cours de {cl['balance']:,} DA")
                
        return {"alerts": alerts if alerts else ["Aucune alerte active."]}

    elif func_name == "run_system_maintenance":
        from app.services.admin_service import run_database_maintenance
        result = run_database_maintenance()
        return {"success": result.get("ok", False), "message": result.get("message", "Maintenance complétée.")}

    elif func_name == "save_backup_settings":
        from app.services.backup_service import save_backup_configuration
        payload = {
            "gdrive_backup_dir": func_args.get("gdrive_backup_dir", ""),
            "backup_snapshot_time": func_args.get("backup_snapshot_time", "02:00"),
            "backup_local_retention": func_args.get("backup_local_retention", 30),
            "backup_event_retention": func_args.get("backup_event_retention", 100),
            "pg_dump_path": func_args.get("pg_dump_path", ""),
        }
        await save_backup_configuration(payload)
        return {"success": True, "message": "Configuration des sauvegardes enregistrée avec succès."}

    elif func_name == "update_app_user":
        from app.services.admin_service import update_user_account
        user_id = int(func_args.get("user_id") or 0)
        role = func_args.get("role", "").strip()
        is_active = bool(func_args.get("is_active"))
        new_password = func_args.get("new_password", "").strip()
        
        await update_user_account(
            user_id=user_id,
            role=role,
            is_active=is_active,
            new_password=new_password
        )
        return {"success": True, "message": f"Utilisateur #{user_id} mis à jour avec succès."}

    elif func_name == "get_export_link":
        import urllib.parse
        et = func_args.get("export_type", "").lower().strip()
        date_from = func_args.get("date_from", "").strip()
        date_to = func_args.get("date_to", "").strip()
        
        if et == "clients":
            url = "/api/v1/clients/export"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter la liste des clients en CSV :\n- [Télécharger l'export Clients]({url})"
            }
        elif et == "reports":
            params = {}
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
            url = f"/reports/export-csv{query_str}"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter le rapport global en CSV :\n- [Télécharger le Rapport]({url})"
            }
        elif et == "audit":
            params = {}
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            
            af = func_args.get("audit_filters") or {}
            if af.get("actor"):
                params["actor"] = af["actor"].strip()
            if af.get("action"):
                params["action"] = af["action"].strip()
            if af.get("entity_type"):
                params["entity_type"] = af["entity_type"].strip()
            if af.get("status"):
                params["status"] = af["status"].strip()
                
            query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
            url = f"/admin/audit/export{query_str}"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter les journaux d'audit en CSV :\n- [Télécharger l'Audit]({url})"
            }
        elif et == "diagnostic":
            url = "/admin/system-status/export"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter le rapport de diagnostic système en JSON :\n- [Télécharger le Rapport Diagnostic]({url})"
            }
            
        return {"error": f"Type d'export '{et}' non reconnu."}

    return {"error": f"Outil '{func_name}' non géré."}
