from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.helpers import unit_choices
from app.core.models import Supplier
from app.modules.purchases.infrastructure.repository import PurchaseRepository, PurchaseDocumentRepository


class PurchaseQueries:
    """Gestion des requêtes en lecture seule (Queries) du module Achats."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.purchase_repo = PurchaseRepository(session)
        self.doc_repo = PurchaseDocumentRepository(session)

    async def list_purchases(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        return await self.purchase_repo.list_purchases_paginated(
            search=search,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )

    async def purchase_form_context(self) -> dict:
        raw_choices = await self.purchase_repo.list_raw_material_choices()
        stmt = select(Supplier).order_by(Supplier.name)
        res = await self.session.execute(stmt)
        suppliers = [dict(s._mapping) for s in res.fetchall()]
        return {
            "suppliers": suppliers,
            "raw_materials": raw_choices,
            "units": unit_choices()
        }

    async def get_purchase_document_context(self, document_id: int) -> Optional[dict]:
        document = await self.doc_repo.get_by_id(document_id)
        if not document:
            return None
        lines = await self.doc_repo.list_lines(document_id)
        return {
            "purchase_document": document,
            "purchase_lines": lines,
        }

    async def get_purchase_edit_context(self, purchase_id: int) -> Optional[dict]:
        purchase = await self.purchase_repo.get_by_id(purchase_id)
        if not purchase:
            return None
        if purchase.get("document_id"):
            context = await self.get_purchase_document_context(int(purchase["document_id"]))
            if context:
                context["redirect_document_id"] = int(purchase["document_id"])
            return context

        return {
            "purchase_document": {
                "id": None,
                "supplier_id": purchase.get("supplier_id"),
                "purchase_date": purchase.get("purchase_date"),
                "notes": purchase.get("notes") or "",
            },
            "purchase_lines": [purchase],
        }
