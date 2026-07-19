# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
import os
from typing import Any, Dict
from app.core.config import BASE_DIR
from app.modules.assistant.tool_actions import sanitize_numeric, _assert_workspace_path

logger = logging.getLogger("fabouanes.assistant")

async def handle_contacts(func_name: str, func_args: dict, session_maker, user_role: str = 'operator') -> Dict[str, Any] | None:

    if func_name == "add_client":
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
            success = False
            async with session_maker() as session:
                service = ClientService(session)
                if not name:
                    existing = await service.get_client(client_id)
                    if existing:
                        name = existing.name
                schema = ClientUpdateSchema(name=name, phone=phone, address=address, notes=notes)
                updated = await service.update_client(client_id, schema)
                if updated:
                    success = True
                    await session.commit()
            if not success:
                return {"error": f"Client {client_id} introuvable."}
            return {"success": True, "message": f"Client {client_id} modifié."}

    elif func_name == "delete_client":
            client_id = int(func_args.get("client_id"))
            from app.modules.clients.service import ClientService
            success = False
            async with session_maker() as session:
                service = ClientService(session)
                success = await service.delete_client(client_id)
                if success:
                    await session.commit()
            if not success:
                return {"error": f"Client {client_id} introuvable ou lié à des opérations."}
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

    elif func_name == "import_client_excel":
            filepath = func_args.get("filepath", "")
            abs_path = os.path.abspath(filepath)
            workspace_dir = os.path.abspath(str(BASE_DIR))
            try:
                _assert_workspace_path(abs_path, workspace_dir)
            except ValueError as e:
                return {"error": str(e)}
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
                _assert_workspace_path(abs_path, workspace_dir)
            except ValueError as e:
                return {"error": str(e)}
    
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
                _assert_workspace_path(abs_path, workspace_dir)
            except ValueError as e:
                return {"error": str(e)}
    
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

    return None
