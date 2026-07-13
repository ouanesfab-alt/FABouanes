# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict

logger = logging.getLogger("fabouanes.assistant")

async def handle_tools(func_name: str, func_args: dict, session_maker, user_role: str = 'operator') -> Dict[str, Any] | None:

    if func_name == "list_user_notes":
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
                    select(FinishedProduct.name, FinishedProduct.stock_qty, FinishedProduct.alert_threshold, FinishedProduct.default_unit)
                    .where(FinishedProduct.stock_qty <= FinishedProduct.alert_threshold, FinishedProduct.alert_threshold > 0)
                )
                for row in finished_res.all():
                    alerts.append(f"Alerte Stock Produit : '{row.name}' est bas ({row.stock_qty} {row.default_unit} restant, seuil: {row.alert_threshold})")
                    
                overdue_clients = await check_overdue_clients(db=session)
                for cl in overdue_clients:
                    alerts.append(f"Alerte Paiement : Client '{cl['name']}' est inactif depuis {int(cl['jours_inactif'] or 0)} jours avec une dette en cours de {cl['balance']:,} DA")
                    
            return {"alerts": alerts if alerts else ["Aucune alerte active."]}

    elif func_name == "redirect_to":
            url = func_args.get("url", "/")
            return {"redirect_url": url}

    elif func_name == "change_theme":
            theme = func_args.get("theme", "light")
            return {"theme": theme}

    return None
