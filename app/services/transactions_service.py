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
)
from app.core.uow import unit_of_work
from app.modules.production.service import update_production_notes  # noqa: F401
from app.utils.pagination import (
    MAX_PAGE_SIZE,
    pagination_context,
    parse_pagination,
)


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
