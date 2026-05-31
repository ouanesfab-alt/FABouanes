from __future__ import annotations

import math
import json
import shutil
import secrets
from time import time
from typing import Any, Dict, List, Optional, Tuple
from werkzeug.utils import secure_filename
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete, func, literal, literal_column, or_

from app.core.models import Client, ClientKey, ClientHistory
from app.core.events import DomainEvent, emit
from app.core.perf_cache import invalidate_client_cache
from app.modules.clients.repository import ClientRepository
from app.modules.clients.schemas_validation import ClientCreateSchema, ClientUpdateSchema
from app.core.storage import IMPORT_DIR, ensure_runtime_dirs
from app.core.helpers import parse_excel_client_file, parse_excel_client_history
from app.services.excel_import_service import parse_client_history_excel

_IMPORT_PREVIEW_TTL_SECONDS = 30 * 60



class ClientService:
    """Asynchronous business service layer for Clients."""

    def __init__(self, session: AsyncSession):
        self.repo = ClientRepository(session)

    async def _decrypt_client(self, client: Optional[Client]) -> Optional[Client]:
        if not client:
            return client
        import base64
        from app.core.security import decrypt_val
        stmt = select(ClientKey.client_id, ClientKey.encryption_key).where(ClientKey.client_id == client.id)
        res = await self.repo.session.execute(stmt)
        row = res.mappings().first()
        key = base64.b64decode(row["encryption_key"]) if row and row.get("encryption_key") else None
        
        client.phone = decrypt_val(client.phone, key)
        client.address = decrypt_val(client.address, key)
        return client

    async def _decrypt_clients(self, clients: List[Client]) -> List[Client]:
        if not clients:
            return clients
        client_ids = [c.id for c in clients if c.id]
        if not client_ids:
            return clients
            
        import base64
        from app.core.security import decrypt_val
        
        stmt = select(ClientKey.client_id, ClientKey.encryption_key).where(ClientKey.client_id.in_(client_ids))
        res = await self.repo.session.execute(stmt)
        keys_map = {}
        for row in res.all():
            keys_map[row[0]] = base64.b64decode(row[1])
            
        for client in clients:
            key = keys_map.get(client.id)
            client.phone = decrypt_val(client.phone, key)
            client.address = decrypt_val(client.address, key)
        return clients

    async def shred_client(self, client_id: int) -> bool:
        """Shreds a client's sensitive PII."""
        client = await self.repo.get_by_id(client_id)
        if not client:
            return False
            
        # Delete key
        await self.repo.session.execute(
            delete(ClientKey).where(ClientKey.client_id == client_id)
        )
        
        # Set phone & address to "[SHREDDED]"
        client.phone = "[SHREDDED]"
        client.address = "[SHREDDED]"
        
        await self.repo.update(client)
        invalidate_client_cache(client_id)
        
        emit(
            DomainEvent(
                "update",
                "client",
                client_id,
                f"Client #{client_id} anonymisé par crypto-shredding",
                after=client.model_dump(),
            )
        )
        return True

    async def get_client(self, client_id: int) -> Optional[Client]:
        """Fetch client by ID."""
        client = await self.repo.get_by_id(client_id)
        return await self._decrypt_client(client)

    async def list_clients(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 50
    ) -> Tuple[List[Client], int]:
        """List paginated clients."""
        clients, total = await self.repo.list_clients(search, page, page_size)
        return await self._decrypt_clients(clients), total

    async def list_clients_with_stats(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 50
    ) -> Tuple[List[dict], int]:
        """Lists clients with calculated statistics and balance from the database view."""
        from sqlalchemy import text
        stmt = select(
            *Client.__table__.columns,
            literal_column("current_balance"),
            literal_column("total_sales"),
            literal_column("total_payments")
        ).select_from(text("clients_with_stats"))
        
        if search:
            stmt = stmt.where(literal_column("search_vector").op("@@")(func.plainto_tsquery('french', search)))
            
        stmt = stmt.add_columns(func.count().over().label("_total_count"))
        
        offset = (page - 1) * page_size
        stmt = (
            stmt.order_by(literal_column("name"))
            .offset(offset)
            .limit(page_size)
        )
        
        res = await self.repo.session.execute(stmt)
        rows = [dict(row._mapping) for row in res.fetchall()]
        
        if rows:
            client_ids = [c["id"] for c in rows if c.get("id")]
            if client_ids:
                import base64
                from app.core.security import decrypt_val
                
                stmt_keys = select(ClientKey.client_id, ClientKey.encryption_key).where(ClientKey.client_id.in_(client_ids))
                res_keys = await self.repo.session.execute(stmt_keys)
                keys_map = {}
                for row in res_keys.all():
                    keys_map[row[0]] = base64.b64decode(row[1])
                    
                for client in rows:
                    key = keys_map.get(client["id"])
                    client["phone"] = decrypt_val(client["phone"], key)
                    client["address"] = decrypt_val(client["address"], key)
                    
        total = int(rows[0]["_total_count"]) if rows else 0
        return rows, total

    async def create_client(self, schema: ClientCreateSchema) -> Client:
        """Create and persist a new client."""
        client = Client(
            name=schema.name,
            phone="",
            address="",
            notes=schema.notes,
            opening_credit=schema.opening_credit,
        )
        created = await self.repo.create(client)

        import os
        import base64
        key = os.urandom(32)
        b64_key = base64.b64encode(key).decode("utf-8")
        
        ck = ClientKey(client_id=created.id, encryption_key=b64_key)
        self.repo.session.add(ck)
        await self.repo.session.commit()

        from app.core.security import encrypt_val
        created.phone = encrypt_val(schema.phone, key)
        created.address = encrypt_val(schema.address, key)
        
        updated = await self.repo.update(created)
        decrypted = await self._decrypt_client(updated)

        # Publish domain event for auditing/logging
        emit(
            DomainEvent(
                "create",
                "client",
                decrypted.id,
                f"Nouveau client créé: {decrypted.name}",
                after=decrypted.model_dump(),
            )
        )
        return decrypted

    async def update_client(
        self, client_id: int, schema: ClientUpdateSchema
    ) -> Optional[Client]:
        """Update properties of an existing client."""
        client = await self.repo.get_by_id(client_id)
        if not client:
            return None

        # Fetch key
        import base64
        stmt_key = select(ClientKey.client_id, ClientKey.encryption_key).where(ClientKey.client_id == client.id)
        res = await self.repo.session.execute(stmt_key)
        row = res.mappings().first()
        key = base64.b64decode(row["encryption_key"]) if row and row.get("encryption_key") else None
        if not key:
            import os
            key = os.urandom(32)
            b64_key = base64.b64encode(key).decode("utf-8")
            ck = ClientKey(client_id=client.id, encryption_key=b64_key)
            self.repo.session.add(ck)
            await self.repo.session.commit()

        from app.core.security import decrypt_val, encrypt_val
        decrypted_before = Client(
            id=client.id,
            name=client.name,
            phone=decrypt_val(client.phone, key),
            address=decrypt_val(client.address, key),
            notes=client.notes,
            opening_credit=client.opening_credit,
            created_at=client.created_at,
            updated_at=client.updated_at
        )
        before_dump = decrypted_before.model_dump()

        client.name = schema.name
        client.phone = encrypt_val(schema.phone, key)
        client.address = encrypt_val(schema.address, key)
        client.notes = schema.notes
        client.opening_credit = schema.opening_credit

        updated = await self.repo.update(client)

        # Invalidate cache for this specific client
        invalidate_client_cache(client_id)

        decrypted_after = await self._decrypt_client(updated)

        # Publish domain event for auditing/logging
        emit(
            DomainEvent(
                "update",
                "client",
                decrypted_after.id,
                f"Client mis à jour: {decrypted_after.name}",
                before=before_dump,
                after=decrypted_after.model_dump(),
            )
        )
        return decrypted_after

    async def delete_client(self, client_id: int) -> bool:
        """Delete an existing client (only if no operations linked)."""
        client = await self.repo.get_by_id(client_id)
        if not client:
            return False

        before_dump = client.model_dump()
        success = await self.repo.delete(client_id)

        if success:
            invalidate_client_cache(client_id)
            emit(
                DomainEvent(
                    "delete",
                    "client",
                    client_id,
                    f"Suppression client #{client_id}",
                    before=before_dump,
                )
            )
        return success

    async def has_operations(self, client_id: int) -> bool:
        """Check if client has linked sales or payments."""
        return await self.repo.has_operations(client_id)

    async def get_client_detail_context(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Build full client detail context with timeline and stats (async)."""
        from app.core.perf_cache import async_cached_result

        async def _load():
            client = await self.get_client(client_id)
            if not client:
                return None

            events = await self.repo.get_timeline(client_id)

            timeline = []
            created_at_str = (
                client.created_at.isoformat()
                if hasattr(client.created_at, "isoformat")
                else str(client.created_at or "")
            )

            if float(client.opening_credit) > 0:
                timeline.append(
                    {
                        "row_id": None,
                        "document_id": None,
                        "sort_sequence": 0,
                        "event_date": created_at_str[:10],
                        "designation": "Credit initial (reprise Excel)",
                        "purchase_amount": float(client.opening_credit),
                        "payment_amount": 0.0,
                        "event_type": "opening",
                    }
                )

            for row in events:
                item = dict(row)
                dt_val = item.get("event_date")
                if hasattr(dt_val, "strftime"):
                    item["event_date"] = dt_val.strftime("%Y-%m-%d")
                elif hasattr(dt_val, "isoformat"):
                    item["event_date"] = dt_val.isoformat()[:10]
                else:
                    item["event_date"] = str(dt_val or "")[:10]

                if item["event_type"] in ("sale_finished", "sale_raw"):
                    suffix = (
                        " (matière première)" if item["event_type"] == "sale_raw" else ""
                    )
                    qty = _format_quantity(item["quantity"])
                    unit = item["unit"] or ""
                    item["designation"] = (
                        f"{item['item_name']}{suffix} - {qty} {unit}".strip()
                    )
                timeline.append(item)

            timeline.sort(
                key=lambda item: (
                    item["event_date"],
                    0 if item["event_type"] in ("opening", "sale_finished", "sale_raw") else 1,
                    int(item.get("sort_sequence") or 0),
                )
            )

            running = 0.0
            for item in timeline:
                running += float(item.get("purchase_amount", 0) or 0)
                running -= float(item.get("payment_amount", 0) or 0)
                item["running_balance"] = running

            total_sales = sum(
                float(item["purchase_amount"])
                for item in timeline
                if item["event_type"] in ("sale_finished", "sale_raw")
            )
            total_advance = sum(
                float(item["purchase_amount"])
                for item in timeline
                if item["event_type"] == "advance"
            )
            total_paid = sum(
                float(item["payment_amount"])
                for item in timeline
                if item["event_type"] == "payment"
            )

            stats = {
                "opening_credit": float(client.opening_credit),
                "total_sales": total_sales,
                "credit_sales_total": float(client.opening_credit) + total_sales,
                "total_paid": total_paid,
                "total_advance": total_advance,
                "current_balance": running,
            }

            # Convert client to dict for template compatibility
            client_dict = {
                "id": client.id,
                "name": client.name,
                "phone": client.phone,
                "address": client.address,
                "notes": client.notes,
                "opening_credit": client.opening_credit,
                "created_at": client.created_at,
                "updated_at": client.updated_at,
            }

            return {
                "client": client_dict,
                "timeline": timeline,
                "stats": stats,
                "client_balance": running,
            }

        return await async_cached_result(("client_detail", int(client_id)), _load, ttl_seconds=30.0)

    async def get_history_page_context(
        self, client_id: int, page: int = 1, page_size: int = 15
    ) -> Optional[Dict[str, Any]]:
        """Build paginated history context for client history page."""
        client = await self.get_client(client_id)
        if not client:
            return None

        rows, total = await self.repo.get_history_paginated(client_id, page, page_size)
        total_pages = math.ceil(total / page_size) if page_size > 0 else 1
        stats = await self.repo.get_history_stats(client_id)

        balance = await self.repo.get_balance(client_id)
        client_balance = balance if balance is not None else float(client.opening_credit)

        client_dict = {
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
            "address": client.address,
            "notes": client.notes,
            "opening_credit": client.opening_credit,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
        }

        return {
            "client": client_dict,
            "client_balance": client_balance,
            "history": rows,
            "stats": stats,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        }

    # --- EXCEL IMPORT LOGIC ---

    def _preview_path(self, token: str):
        clean = "".join(ch for ch in str(token or "") if ch.isalnum() or ch in {"-", "_"})
        if not clean:
            raise ValueError("Jeton de previsualisation invalide")
        return IMPORT_DIR / f"client_import_preview_{clean}.json"

    def _save_client_import_preview(self, rows: list[dict]) -> str:
        ensure_runtime_dirs()
        token = secrets.token_urlsafe(24)
        payload = {"created_at": time(), "rows": rows}
        self._preview_path(token).write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return token

    def _load_client_import_preview(self, token: str) -> list[dict]:
        path = self._preview_path(token)
        if not path.exists():
            raise ValueError("Previsualisation expiree ou introuvable")
        payload = json.loads(path.read_text(encoding="utf-8"))
        created_at = float(payload.get("created_at") or 0)
        if created_at <= 0 or (time() - created_at) > _IMPORT_PREVIEW_TTL_SECONDS:
            try:
                path.unlink()
            except Exception:
                pass
            raise ValueError("Previsualisation expiree")
        rows = payload.get("rows") or []
        if not isinstance(rows, list):
            raise ValueError("Previsualisation invalide")
        return rows

    def _discard_client_import_preview(self, token: str) -> None:
        try:
            self._preview_path(token).unlink()
        except Exception:
            pass

    async def _parse_client_import_files(self, files):
        ensure_runtime_dirs()
        parsed_rows = []
        errors = []
        seen: set[str] = set()
        duplicates: list[str] = []
        for index, uploaded in enumerate(files):
            if not uploaded or not uploaded.filename:
                continue
            filename = secure_filename(uploaded.filename)
            if not filename.lower().endswith((".xlsx", ".xlsm")):
                errors.append(f"{filename}: format non supporte")
                continue
            temp_path = IMPORT_DIR / f"{index}_{filename}"
            try:
                self._save_uploaded_file(uploaded, temp_path)
                parsed = parse_excel_client_file(temp_path)
                last = parse_excel_client_history(temp_path)
                opening = last["last_balance"] if last["last_balance"] > 0 else parsed["opening_credit"]
                name_key = str(parsed["name"]).strip().casefold()
                if not name_key:
                    errors.append(f"{filename}: nom client introuvable")
                    continue
                if name_key in seen:
                    duplicates.append(parsed["name"])
                    continue
                seen.add(name_key)
                
                existing = await self.repo.find_by_name(str(parsed["name"]))
                parsed_rows.append(
                    {
                        "filename": filename,
                        "name": parsed["name"],
                        "phone": parsed["phone"],
                        "address": parsed["address"],
                        "opening_credit": opening,
                        "history_count": int(last.get("history_count", 0) or 0),
                        "status": "update" if existing else "create",
                        "existing_id": int(existing.id) if existing else None,
                    }
                )
            except Exception as exc:
                errors.append(f"{filename}: {exc}")
            finally:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    pass
        return {"rows": parsed_rows, "errors": errors, "duplicates": duplicates}

    def _save_uploaded_file(self, uploaded, temp_path) -> None:
        if hasattr(uploaded, "save"):
            uploaded.save(temp_path)
            return
        file_obj = getattr(uploaded, "file", None)
        if file_obj is not None:
            try:
                file_obj.seek(0)
            except Exception:
                pass
            with open(temp_path, "wb") as output:
                shutil.copyfileobj(file_obj, output)
            return
        content = uploaded if isinstance(uploaded, (bytes, bytearray)) else bytes(uploaded)
        with open(temp_path, "wb") as output:
            output.write(content)

    async def preview_clients_from_files(self, files):
        parsed = await self._parse_client_import_files(files)
        token = ""
        if parsed["rows"] and not parsed["errors"] and not parsed["duplicates"]:
            token = self._save_client_import_preview(parsed["rows"])
        return {
            "rows": parsed["rows"],
            "errors": parsed["errors"],
            "duplicates": parsed["duplicates"],
            "created": sum(1 for row in parsed["rows"] if row["status"] == "create"),
            "updated": sum(1 for row in parsed["rows"] if row["status"] == "update"),
            "token": token,
        }

    async def _import_parsed_client_rows(self, rows: list[dict]):
        seen: set[str] = set()
        duplicate_names: list[str] = []
        for row in rows:
            name_key = str(row.get("name") or "").strip().casefold()
            if not name_key:
                duplicate_names.append(str(row.get("filename") or "ligne sans nom"))
            elif name_key in seen:
                duplicate_names.append(str(row.get("name") or name_key))
            seen.add(name_key)
        if duplicate_names:
            return {
                "created": 0,
                "updated": 0,
                "errors": [f"Doublon dans les fichiers: {name}" for name in duplicate_names],
                "preview": rows,
            }

        created = 0
        updated = 0
        errors = []
        try:
            # Pre-load all existing clients in one query to avoid N calls.
            stmt = select(Client)
            res = await self.repo.session.execute(stmt)
            all_clients = res.scalars().all()
            
            # Decrypt existing clients to compare phone and address
            clients_list = list(all_clients)
            await self._decrypt_clients(clients_list)

            # Build lookup by normalized name
            clients_by_name: dict[str, Client] = {}
            for c in clients_list:
                key = str(c.name).strip().casefold()
                clients_by_name[key] = c

            for row in rows:
                name_key = str(row["name"]).strip().casefold()
                existing = clients_by_name.get(name_key)
                if existing:
                    existing_id = int(existing.id)
                    phone_to_set = existing.phone or row.get("phone") or ""
                    address_to_set = existing.address or row.get("address") or ""
                    schema = ClientUpdateSchema(
                        name=existing.name or row.get("name"),
                        phone=phone_to_set,
                        address=address_to_set,
                        notes=existing.notes or "",
                        opening_credit=row["opening_credit"]
                    )
                    await self.update_client(existing_id, schema)
                    updated += 1
                else:
                    schema = ClientCreateSchema(
                        name=row["name"],
                        phone=row["phone"] or "",
                        address=row["address"] or "",
                        notes="",
                        opening_credit=row["opening_credit"]
                    )
                    await self.create_client(schema)
                    created += 1
        except Exception as exc:
            errors.append(f"Import annule: {exc}")
            created = 0
            updated = 0
        
        if not errors:
            from app.core.storage import mark_backup_needed
            mark_backup_needed("import_excel")
        return {"created": created, "updated": updated, "errors": errors, "preview": rows}

    async def import_clients_from_preview(self, token: str):
        try:
            rows = self._load_client_import_preview(token)
        except Exception as exc:
            return {"created": 0, "updated": 0, "errors": [str(exc)], "preview": []}
        result = await self._import_parsed_client_rows(rows)
        if not result["errors"]:
            self._discard_client_import_preview(token)
        return result

    async def import_clients_from_files(self, files):
        parsed = await self._parse_client_import_files(files)
        if parsed["errors"] or parsed["duplicates"]:
            errors = list(parsed["errors"])
            errors.extend(f"Doublon dans les fichiers: {name}" for name in parsed["duplicates"])
            return {"created": 0, "updated": 0, "errors": errors, "preview": parsed["rows"]}
        return await self._import_parsed_client_rows(parsed["rows"])

    # --- CLIENT HISTORY EXCEL IMPORT ---

    async def import_client_history_from_excel(
        self,
        file_path: str,
        client_id: int | None = None,
        force_reimport: bool = True
    ) -> dict:
        """
        Importe l'historique complet d'un client à partir de son fichier Excel.
        """
        # 1. Parser le fichier Excel
        data = parse_client_history_excel(file_path)
        client_name = data["client_name"]
        solde_final = data["solde_final"]
        rows = data["rows"]

        # 2. Résoudre ou créer le client
        if client_id is not None:
            # Vérifier que le client existe
            client = await self.repo.get_by_id(client_id)
            if not client:
                raise ValueError(f"Le client spécifié (ID {client_id}) n'existe pas.")
        else:
            # Recherche par nom (insensible à la casse, espaces nettoyés)
            client = await self.repo.find_by_name(client_name)
            if client:
                client_id = client.id
            else:
                # Créer le client avec le solde final comme opening_credit
                schema = ClientCreateSchema(
                    name=client_name,
                    phone="",
                    address="",
                    notes="",
                    opening_credit=solde_final
                )
                created = await self.create_client(schema)
                client_id = created.id

        # 3. Vérifier s'il y a déjà un historique importé
        stmt_hist = (
            select(literal(1))
            .where(ClientHistory.client_id == client_id)
            .where(ClientHistory.source == 'import_excel')
            .limit(1)
        )
        res_hist = await self.repo.session.execute(stmt_hist)
        existing_history = res_hist.first() is not None

        if existing_history:
            if not force_reimport:
                raise ValueError(
                    f"Un historique Excel importé existe déjà pour le client '{client_name}' "
                    "et force_reimport est désactivé."
                )
            # Supprimer l'ancien historique Excel importé
            stmt_del = delete(ClientHistory).where(
                ClientHistory.client_id == client_id,
                ClientHistory.source == 'import_excel'
            )
            await self.repo.session.execute(stmt_del)

        # 4. Mettre à jour le solde (opening_credit) du client
        client_to_update = await self.repo.get_by_id(client_id)
        if client_to_update:
            client_to_update.opening_credit = solde_final
            self.repo.session.add(client_to_update)

        # 5. Insérer en lot les nouvelles lignes dans client_history (batch INSERT)
        if rows:
            from datetime import date, datetime
            history_objs = []
            for r in rows:
                dt_val = r["date"]
                if isinstance(dt_val, str):
                    try:
                        op_date = date.fromisoformat(dt_val.strip())
                    except ValueError:
                        try:
                            op_date = datetime.strptime(dt_val.strip(), "%Y-%m-%d").date()
                        except Exception:
                            op_date = date.today()
                elif isinstance(dt_val, datetime):
                    op_date = dt_val.date()
                elif isinstance(dt_val, date):
                    op_date = dt_val
                else:
                    op_date = date.today()

                history_objs.append(
                    ClientHistory(
                        client_id=client_id,
                        operation_date=op_date,
                        designation=r["designation"],
                        montant_achat=r["montant_achat"],
                        montant_verse=r["montant_verse"],
                        solde_cumule=r["solde_cumule"],
                        ordre_import=r["ordre_import"],
                        source='import_excel'
                    )
                )
            self.repo.session.add_all(history_objs)

        # Commit to persist
        await self.repo.session.commit()

        return {
            "client_id": client_id,
            "client_name": client_name,
            "nb_lignes": len(rows),
            "solde_final": solde_final,
        }



def _format_quantity(value) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0.00"
    return f"{number:.2f}".rstrip("0").rstrip(".")
