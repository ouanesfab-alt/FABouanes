"""
Service métier de comptabilité et de transactions / opérations unifiées.
"""

from __future__ import annotations

from datetime import datetime as dt_class
from typing import Any

from sqlalchemy import (
    Integer,
    Numeric,
    String,
    and_,
    case,
    cast,
    func,
    literal,
    or_,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal

from app.core.model_utils import to_gmt1
from app.core.models import (
    Client,
    FinishedProduct,
    Payment,
    Purchase,
    RawMaterial,
    RawSale,
    Sale,
    Supplier,
    SupplierPayment,
)
from app.core.uow import unit_of_work
from app.modules.accounting.scf_service import SCFService
from app.modules.production.service import update_production_notes  # noqa: F401
from app.utils.pagination import (
    MAX_PAGE_SIZE,
    pagination_context,
    parse_pagination,
)


class AccountingService:
    """Service centralisant les opérations comptables et le SCF."""

    scf = SCFService

    @staticmethod
    async def get_transactions(
        filter_type: str = "all",
        filter_name: str = "",
        filter_date: str = "",
        filter_operation: str = "",
        args=None,
        path: str = "/operations",
        db: AsyncSession | None = None,
    ) -> dict:
        return await transactions_context(
            filter_type=filter_type,
            filter_name=filter_name,
            filter_date=filter_date,
            filter_operation=filter_operation,
            args=args,
            path=path,
            db=db,
        )

    @staticmethod
    async def reconcile_client_balances(db: AsyncSession | None = None) -> dict:
        from app.modules.admin.system_service import reconcile_client_balances as rcb
        if db is not None:
            return await rcb(db)
        async with unit_of_work(db) as session:
            return await rcb(session)

    @staticmethod
    async def reconcile_supplier_balances(db: AsyncSession | None = None) -> dict:
        return await reconcile_supplier_balances(db)

    @staticmethod
    async def reconcile_stock_balance(db: AsyncSession | None = None) -> dict:
        return await reconcile_stock_balance(db)

    @staticmethod
    async def reconcile_scf_balance(db: AsyncSession | None = None) -> dict:
        return await reconcile_scf_balance(db)

    @staticmethod
    async def reconcile_financial_system(db: AsyncSession | None = None) -> dict:
        return await reconcile_financial_system(db)


async def transactions_context(
    filter_type: str = "all",
    filter_name: str = "",
    filter_date: str = "",
    filter_operation: str = "",
    args=None,
    path: str = "/operations",
    db: AsyncSession | None = None,
) -> dict:
    async with unit_of_work(db) as session:
        return await _transactions_context_impl(
            filter_type, filter_name, filter_date, filter_operation, args, path, session
        )


async def _transactions_context_impl(
    filter_type: str,
    filter_name: str,
    filter_date: str,
    filter_operation: str,
    args: Any,
    path: str,
    db: AsyncSession,
) -> dict:
    name_filter = (filter_name or "").strip().lower()
    date_filter = (filter_date or "").strip()
    operation_filter = (filter_operation or "").strip().lower()

    db_date_filter = None
    if date_filter:
        try:
            db_date_filter = dt_class.strptime(date_filter, "%Y-%m-%d").date()
        except ValueError:
            pass

    queries = []

    # 1. Purchases query
    if filter_type in ("all", "purchase"):
        p_unit_raw = func.coalesce(Purchase.unit, FinishedProduct.default_unit, RawMaterial.unit, "kg")
        p_unit_lower = func.lower(p_unit_raw)
        sac_weight = func.coalesce(
            func.nullif(func.regexp_replace(p_unit_raw, r"[^0-9.]", "", "g"), ""),
            "50",
        )
        sac_weight_num = cast(sac_weight, Numeric)

        p_qty = case(
            (p_unit_lower.like("sac%"), Purchase.quantity / sac_weight_num),
            (p_unit_lower.in_(["qt", "quintal"]), Purchase.quantity / 100.0),
            else_=Purchase.quantity,
        )
        p_price = case(
            (p_unit_lower.like("sac%"), Purchase.unit_price * sac_weight_num),
            (p_unit_lower.in_(["qt", "quintal"]), Purchase.unit_price * 100.0),
            else_=Purchase.unit_price,
        )
        p_designation = case(
            (Purchase.finished_product_id.isnot(None), FinishedProduct.name),
            else_=RawMaterial.name,
        )

        p_stmt = (
            select(
                literal("Achat").label("tx_type"),
                literal("purchase").label("tx_kind"),
                Purchase.id.label("id"),
                Purchase.purchase_date.label("tx_date"),
                func.coalesce(Supplier.name, "-").label("partner_name"),
                p_designation.label("designation"),
                p_qty.label("quantity"),
                p_unit_raw.label("unit"),
                p_price.label("unit_price"),
                Purchase.total.label("total"),
                cast(None, Numeric).label("paid"),
                cast(None, Numeric).label("due"),
                Purchase.document_id.label("document_id"),
                Purchase.created_at.label("tx_created_at"),
            )
            .select_from(Purchase)
            .outerjoin(Supplier, Supplier.id == Purchase.supplier_id)
            .outerjoin(RawMaterial, RawMaterial.id == Purchase.raw_material_id)
            .outerjoin(FinishedProduct, FinishedProduct.id == Purchase.finished_product_id)
        )

        if db_date_filter:
            p_stmt = p_stmt.where(Purchase.purchase_date == db_date_filter)
        if name_filter:
            like_pat = f"%{name_filter}%"
            p_stmt = p_stmt.where(
                or_(
                    func.lower(func.coalesce(Supplier.name, "")).like(like_pat),
                    func.lower(func.coalesce(RawMaterial.name, "")).like(like_pat),
                    func.lower(func.coalesce(FinishedProduct.name, "")).like(like_pat),
                )
            )
        if operation_filter:
            p_stmt = p_stmt.where(func.lower(literal("Achat")).like(f"%{operation_filter}%"))

        queries.append(p_stmt)

    # 2. Sales query (finished + raw)
    if filter_type in ("all", "sale"):
        sales_finished = (
            select(
                Sale.id.label("id"),
                Sale.document_id.label("document_id"),
                literal("finished").label("row_kind"),
                Sale.sale_date.label("sale_date"),
                Client.name.label("client_name"),
                FinishedProduct.name.label("item_name"),
                Sale.quantity.label("quantity"),
                Sale.unit.label("unit"),
                Sale.unit_price.label("unit_price"),
                Sale.total.label("total"),
                Sale.amount_paid.label("amount_paid"),
                Sale.balance_due.label("balance_due"),
                Sale.created_at.label("created_at"),
            )
            .select_from(Sale)
            .outerjoin(Client, Client.id == Sale.client_id)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
        )

        sales_raw = (
            select(
                RawSale.id.label("id"),
                RawSale.document_id.label("document_id"),
                literal("raw").label("row_kind"),
                RawSale.sale_date.label("sale_date"),
                Client.name.label("client_name"),
                RawMaterial.name.label("item_name"),
                RawSale.quantity.label("quantity"),
                RawSale.unit.label("unit"),
                RawSale.unit_price.label("unit_price"),
                RawSale.total.label("total"),
                RawSale.amount_paid.label("amount_paid"),
                RawSale.balance_due.label("balance_due"),
                RawSale.created_at.label("created_at"),
            )
            .select_from(RawSale)
            .outerjoin(Client, Client.id == RawSale.client_id)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
        )

        sales_union = union_all(sales_finished, sales_raw).subquery("x")

        s_stmt = select(
            literal("Vente").label("tx_type"),
            case(
                (sales_union.c.row_kind == "finished", literal("sale_finished")),
                else_=literal("sale_raw"),
            ).label("tx_kind"),
            sales_union.c.id.label("id"),
            sales_union.c.sale_date.label("tx_date"),
            func.coalesce(sales_union.c.client_name, "-").label("partner_name"),
            sales_union.c.item_name.label("designation"),
            sales_union.c.quantity.label("quantity"),
            sales_union.c.unit.label("unit"),
            sales_union.c.unit_price.label("unit_price"),
            sales_union.c.total.label("total"),
            sales_union.c.amount_paid.label("paid"),
            sales_union.c.balance_due.label("due"),
            sales_union.c.document_id.label("document_id"),
            sales_union.c.created_at.label("tx_created_at"),
        ).select_from(sales_union)

        if db_date_filter:
            s_stmt = s_stmt.where(sales_union.c.sale_date == db_date_filter)
        if name_filter:
            like_pat = f"%{name_filter}%"
            s_stmt = s_stmt.where(
                or_(
                    func.lower(func.coalesce(sales_union.c.client_name, "")).like(like_pat),
                    func.lower(sales_union.c.item_name).like(like_pat),
                )
            )
        if operation_filter:
            s_stmt = s_stmt.where(func.lower(literal("Vente")).like(f"%{operation_filter}%"))

        queries.append(s_stmt)

    # 3. Payments query
    if filter_type in ("all", "payment"):
        pay_designation = case(
            (
                and_(Payment.sale_kind == "finished", Payment.sale_id.isnot(None)),
                literal("Versement vente #") + cast(Payment.sale_id, String),
            ),
            (
                and_(Payment.sale_kind == "raw", Payment.raw_sale_id.isnot(None)),
                literal("Versement vente matiere #") + cast(Payment.raw_sale_id, String),
            ),
            (
                Payment.payment_type == "avance",
                literal("Avance client"),
            ),
            else_=literal("Versement client"),
        )

        pay_type_label = case(
            (Payment.payment_type == "avance", literal("Avance")),
            else_=literal("Versement"),
        )

        pay_stmt = (
            select(
                pay_type_label.label("tx_type"),
                literal("payment").label("tx_kind"),
                Payment.id.label("id"),
                Payment.payment_date.label("tx_date"),
                Client.name.label("partner_name"),
                pay_designation.label("designation"),
                cast(None, Numeric).label("quantity"),
                cast(None, String).label("unit"),
                cast(None, Numeric).label("unit_price"),
                Payment.amount.label("total"),
                Payment.amount.label("paid"),
                cast(None, Numeric).label("due"),
                cast(None, Integer).label("document_id"),
                Payment.created_at.label("tx_created_at"),
            )
            .select_from(Payment)
            .join(Client, Client.id == Payment.client_id)
        )

        if db_date_filter:
            pay_stmt = pay_stmt.where(Payment.payment_date == db_date_filter)
        if name_filter:
            like_pat = f"%{name_filter}%"
            pay_stmt = pay_stmt.where(
                or_(
                    func.lower(func.coalesce(Client.name, "")).like(like_pat),
                    func.lower(
                        case(
                            (Payment.payment_type == "avance", literal("Avance client")),
                            else_=literal("Versement client"),
                        )
                    ).like(like_pat),
                )
            )
        if operation_filter:
            pay_stmt = pay_stmt.where(
                func.lower(
                    case(
                        (Payment.payment_type == "avance", literal("Avance")),
                        else_=literal("Versement"),
                    )
                ).like(f"%{operation_filter}%")
            )

        queries.append(pay_stmt)

    if not queries:
        page, page_size, _ = parse_pagination(args)
        return {
            "transactions": [],
            "filter_type": filter_type,
            "filter_name": filter_name,
            "filter_date": filter_date,
            "filter_operation": filter_operation,
            "pagination": pagination_context(path, args, total=0, page=page, page_size=page_size),
        }

    combined = union_all(*queries).subquery("t")

    ordered_stmt = select(combined).order_by(
        combined.c.tx_date.desc(),
        combined.c.tx_created_at.desc(),
        combined.c.id.desc(),
    )

    requested_size = int((args or {}).get("page_size", 0) or 0)
    page, page_size, offset = parse_pagination(args)
    if requested_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE

    count_stmt = select(func.count()).select_from(combined)
    count_res = await db.execute(count_stmt)
    total = int(count_res.scalar() or 0)

    paged_stmt = ordered_stmt.offset(offset).limit(page_size)
    rows_res = await db.execute(paged_stmt)
    rows = rows_res.all()

    formatted_rows = []
    for row in rows:
        row_dict = dict(row._mapping)
        tx_created = to_gmt1(row_dict.get("tx_created_at"))
        if hasattr(tx_created, "strftime"):
            row_dict["tx_time"] = tx_created.strftime("%H:%M")
        elif isinstance(tx_created, str):
            row_dict["tx_time"] = tx_created.split()[1][:5] if " " in tx_created else ""
        else:
            row_dict["tx_time"] = ""
        formatted_rows.append(row_dict)

    pagination = pagination_context(path, args, total=total, page=page, page_size=page_size)

    return {
        "transactions": formatted_rows,
        "filter_type": filter_type,
        "filter_name": filter_name,
        "filter_date": filter_date,
        "filter_operation": filter_operation,
        "pagination": pagination,
    }


__all__ = [
    "AccountingService",
    "SCFService",
    "transactions_context",
    "_transactions_context_impl",
    "update_production_notes",
    "reconcile_supplier_balances",
    "reconcile_stock_balance",
    "reconcile_scf_balance",
    "reconcile_financial_system",
]


async def reconcile_supplier_balances(db: AsyncSession | None = None) -> dict:
    """
    Vérifie l'exactitude des soldes et engagements fournisseurs :
    Total des achats effectués vs total des versements émis au fournisseur.
    """
    try:
        async with unit_of_work(db) as session:
            stmt = (
                select(
                    Supplier.id,
                    Supplier.name,
                    func.coalesce(func.sum(Purchase.total), 0).label("total_purchased"),
                )
                .outerjoin(Purchase, Purchase.supplier_id == Supplier.id)
                .group_by(Supplier.id, Supplier.name)
            )
            purchases_res = await session.execute(stmt)
            purchases_map = {row[0]: (row[1], Decimal(str(row[2]))) for row in purchases_res.all()}

            sp_stmt = (
                select(
                    SupplierPayment.supplier_id,
                    func.coalesce(func.sum(SupplierPayment.amount), 0).label("total_paid"),
                )
                .group_by(SupplierPayment.supplier_id)
            )
            sp_res = await session.execute(sp_stmt)
            payments_map = {row[0]: Decimal(str(row[1])) for row in sp_res.all()}

            discrepancies = []
            all_supplier_ids = set(purchases_map.keys()) | set(payments_map.keys())
            for s_id in sorted(all_supplier_ids):
                name, purchased = purchases_map.get(s_id, ("Fournisseur Inconnu", Decimal("0.00")))
                paid = payments_map.get(s_id, Decimal("0.00"))
                balance = purchased - paid
                # Surplus anormal de versement (dette négative au-delà d'un centime)
                if balance < Decimal("-0.01"):
                    discrepancies.append(
                        {
                            "supplier_id": s_id,
                            "name": name,
                            "total_purchased": float(purchased),
                            "total_paid": float(paid),
                            "balance_due": float(balance),
                            "anomaly": "Surplus de paiement fournisseur supérieur aux achats enregistrés",
                        }
                    )

            return {
                "ok": len(discrepancies) == 0,
                "status": "Conforme" if not discrepancies else "Anomalie fournisseur détectée",
                "count": len(discrepancies),
                "discrepancies": discrepancies,
            }
    except Exception as exc:
        return {
            "ok": False,
            "status": "Erreur audit fournisseurs",
            "error": str(exc),
            "count": 0,
            "discrepancies": [],
        }


async def reconcile_stock_balance(db: AsyncSession | None = None) -> dict:
    """
    Audit de cohérence physique et valorisation des stocks :
    Contrôle l'absence de stocks négatifs et la présence d'un Coût Moyen Pondéré (PMP) valide.
    """
    try:
        async with unit_of_work(db) as session:
            discrepancies = []

            # 1. Produits finis
            fp_res = await session.execute(select(FinishedProduct))
            for fp in fp_res.scalars().all():
                if fp.stock_qty < Decimal("0.00"):
                    discrepancies.append(
                        {
                            "item_kind": "finished",
                            "item_id": fp.id,
                            "name": fp.name,
                            "stock_qty": float(fp.stock_qty),
                            "anomaly": "Stock négatif interdit",
                        }
                    )
                if fp.avg_cost <= Decimal("0.00") and fp.stock_qty > Decimal("0.00"):
                    discrepancies.append(
                        {
                            "item_kind": "finished",
                            "item_id": fp.id,
                            "name": fp.name,
                            "avg_cost": float(fp.avg_cost),
                            "anomaly": "Coût Moyen Pondéré (PMP) manquant sur du stock physique",
                        }
                    )

            # 2. Matières premières
            rm_res = await session.execute(select(RawMaterial))
            for rm in rm_res.scalars().all():
                if rm.stock_qty < Decimal("0.00"):
                    discrepancies.append(
                        {
                            "item_kind": "raw",
                            "item_id": rm.id,
                            "name": rm.name,
                            "stock_qty": float(rm.stock_qty),
                            "anomaly": "Stock négatif interdit",
                        }
                    )
                if rm.avg_cost <= Decimal("0.00") and rm.stock_qty > Decimal("0.00"):
                    discrepancies.append(
                        {
                            "item_kind": "raw",
                            "item_id": rm.id,
                            "name": rm.name,
                            "avg_cost": float(rm.avg_cost),
                            "anomaly": "Coût Moyen Pondéré (PMP) manquant sur du stock physique",
                        }
                    )

            return {
                "ok": len(discrepancies) == 0,
                "status": "Conforme" if not discrepancies else "Anomalie de stock détectée",
                "count": len(discrepancies),
                "discrepancies": discrepancies,
            }
    except Exception as exc:
        return {
            "ok": False,
            "status": "Erreur audit stock",
            "error": str(exc),
            "count": 0,
            "discrepancies": [],
        }


async def reconcile_scf_balance(db: AsyncSession | None = None) -> dict:
    """
    Vérifie l'équilibre strict de la Balance Générale du SCF (partie double).
    """
    try:
        async with unit_of_work(db) as session:
            balance = await SCFService.get_balance_generale(db=session)
            total_debiteur = sum(acc.get("solde_debiteur", 0.0) for acc in balance)
            total_crediteur = sum(acc.get("solde_crediteur", 0.0) for acc in balance)
            diff = round(abs(total_debiteur - total_crediteur), 2)
            is_ok = diff <= 0.05
            return {
                "ok": is_ok,
                "status": "Conforme" if is_ok else "Déséquilibre balance SCF",
                "total_debiteur": total_debiteur,
                "total_crediteur": total_crediteur,
                "imbalance": diff,
                "count": 0 if is_ok else 1,
                "discrepancies": [] if is_ok else [{"imbalance": diff, "total_debiteur": total_debiteur, "total_crediteur": total_crediteur}],
            }
    except Exception as exc:
        return {
            "ok": False,
            "status": "Erreur audit SCF",
            "error": str(exc),
            "total_debiteur": 0.0,
            "total_crediteur": 0.0,
            "imbalance": 0.0,
            "count": 0,
            "discrepancies": [],
        }



async def reconcile_financial_system(db: AsyncSession | None = None) -> dict:
    """
    Exécute un audit financier global à 360° :
    1. Soldes et créances clients
    2. Soldes et dettes fournisseurs
    3. Cohérence physique et valorisation des stocks
    4. Partie double et équilibre du SCF
    """
    from datetime import datetime
    from app.modules.admin.system_service import reconcile_client_balances as rcb

    async with unit_of_work(db) as session:
        clients_report = await rcb(session)
        suppliers_report = await reconcile_supplier_balances(session)
        stock_report = await reconcile_stock_balance(session)
        scf_report = await reconcile_scf_balance(session)

        total_anomalies = (
            clients_report.get("count", 0)
            + suppliers_report.get("count", 0)
            + stock_report.get("count", 0)
            + scf_report.get("count", 0)
        )
        all_ok = total_anomalies == 0

        summary_msg = (
            "✅ Audit financier 360° conforme : Tous les soldes, stocks et états comptables sont intègres."
            if all_ok
            else f"⚠️ {total_anomalies} anomalie(s) ou écart(s) financier(s) détecté(s)."
        )

        return {
            "ok": all_ok,
            "status": "Conforme" if all_ok else f"{total_anomalies} anomalie(s) détectée(s)",
            "summary": summary_msg,
            "timestamp": datetime.now().isoformat(),
            "clients": clients_report,
            "suppliers": suppliers_report,
            "stock": stock_report,
            "scf": scf_report,
            "total_anomalies": total_anomalies,
        }

