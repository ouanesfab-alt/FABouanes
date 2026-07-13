from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.helpers import unit_choices
from app.modules.sales.repository import SaleRepository, SaleDocumentRepository

class SalesQueries:
    """Gestion des requêtes en lecture seule (Queries) du module Sales."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.sale_repo = SaleRepository(session)
        self.doc_repo = SaleDocumentRepository(session)

    async def list_sales(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        return await self.sale_repo.list_sales_paginated(
            search=search,
            date_from=date_from,
            date_to=date_to,
            kind=kind,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def sale_form_context(self) -> dict:
        sellable = await self.sale_repo.list_sellable_items()
        return {"sellable_items": sellable, "units": unit_choices()}

    async def get_sale_document_context(self, document_id: int) -> Optional[dict]:
        document = await self.doc_repo.get_by_id(document_id)
        if not document:
            return None
        lines = await self.doc_repo.list_lines(document_id)
        refs = {(str(line["row_kind"]), int(line["row_id"])) for line in lines}
        has_linked = False
        if document.client_id and refs:
            has_linked = await self.doc_repo.document_has_linked_payments(document_id, int(document.client_id), refs)

        return {
            "sale_document": document.model_dump(),
            "sale_lines": lines,
            "has_linked_payments": has_linked,
        }

    async def get_sale_edit_context(self, kind: str, row_id: int) -> Optional[dict]:
        sale = await self.sale_repo.get_sale_detail(kind, row_id)
        if not sale:
            return None
        if sale.get("document_id"):
            context = await self.get_sale_document_context(int(sale["document_id"]))
            if context:
                context["redirect_document_id"] = int(sale["document_id"])
            return context

        return {
            "sale_document": {
                "id": None,
                "client_id": sale.get("client_id"),
                "sale_type": sale.get("sale_type"),
                "sale_date": sale.get("sale_date"),
                "notes": sale.get("notes") or "",
            },
            "sale_lines": [
                {
                    "row_id": int(sale["id"]),
                    "document_id": None,
                    "row_kind": str(sale["row_kind"]),
                    "item_key": str(sale["item_key"]),
                    "item_name": str(sale["item_name"]),
                    "item_kind": "Produit final" if sale["row_kind"] == "finished" else "Matière première",
                    "quantity": float(sale["quantity"]),
                    "unit": str(sale["unit"]),
                    "unit_price": float(sale["unit_price"]),
                    "total": float(sale["total"]),
                    "amount_paid": float(sale["amount_paid"]),
                    "balance_due": float(sale["balance_due"]),
                    "custom_item_name": str(sale["custom_item_name"] or ""),
                }
            ],
            "has_linked_payments": False,
        }
