from __future__ import annotations

from fabouanes.fastapi_compat import render_template, request

from fabouanes.core.db_access import query_db
from fabouanes.core.decorators import login_required
from fabouanes.routes.route_utils import bind_route


def register_transaction_routes(app):
    @login_required
    def transactions():
        rows = query_db(
            """
            SELECT * FROM (
                SELECT 'Achat' AS tx_type, 'purchase' AS tx_kind, p.id, p.purchase_date AS tx_date,
                       COALESCE(s.name, '-') AS partner_name, COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS designation,
                       CASE
                           WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                           WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                           ELSE p.quantity
                       END AS quantity,
                       COALESCE(p.unit, r.unit, 'kg') AS unit,
                       CASE
                           WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                           WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                           ELSE p.unit_price
                       END AS unit_price,
                       p.total, NULL AS paid, NULL AS due, p.document_id AS document_id
                FROM purchases p
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                JOIN raw_materials r ON r.id = p.raw_material_id
                UNION ALL
                SELECT 'Vente' AS tx_type,
                       CASE WHEN x.row_kind = 'finished' THEN 'sale_finished' ELSE 'sale_raw' END AS tx_kind,
                       x.id, x.sale_date AS tx_date, COALESCE(x.client_name, '-') AS partner_name, x.item_name AS designation,
                       x.quantity, x.unit, x.unit_price, x.total, x.amount_paid AS paid, x.balance_due AS due, x.document_id AS document_id
                FROM (
                    SELECT s.id, s.document_id, 'finished' AS row_kind, s.sale_date, c.name AS client_name, f.name AS item_name, s.quantity, s.unit, s.unit_price, s.total, s.amount_paid, s.balance_due
                    FROM sales s
                    LEFT JOIN clients c ON c.id = s.client_id
                    JOIN finished_products f ON f.id = s.finished_product_id
                    UNION ALL
                    SELECT rs.id, rs.document_id, 'raw' AS row_kind, rs.sale_date, c.name AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, rs.quantity, rs.unit, rs.unit_price, rs.total, rs.amount_paid, rs.balance_due
                    FROM raw_sales rs
                    LEFT JOIN clients c ON c.id = rs.client_id
                    JOIN raw_materials r ON r.id = rs.raw_material_id
                ) x
                UNION ALL
                SELECT CASE WHEN p.payment_type = 'avance' THEN 'Avance' ELSE 'Versement' END AS tx_type, 'payment' AS tx_kind,
                       p.id, p.payment_date AS tx_date, c.name AS partner_name,
                       CASE
                           WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Versement vente #' || p.sale_id
                           WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Versement vente matiere #' || p.raw_sale_id
                           ELSE CASE WHEN p.payment_type = 'avance' THEN 'Avance client' ELSE 'Versement client' END
                       END AS designation,
                       NULL AS quantity, NULL AS unit, NULL AS unit_price, p.amount AS total, p.amount AS paid, NULL AS due, NULL AS document_id
                FROM payments p
                JOIN clients c ON c.id = p.client_id
            ) t
            ORDER BY tx_date DESC, id DESC
            """
        )

        filter_type = request.args.get("type", "all")
        filter_name = (request.args.get("name") or "").strip().lower()
        filter_date = (request.args.get("date") or "").strip()
        filter_operation = (request.args.get("operation") or "").strip().lower()

        filtered_rows = []
        for row in rows:
            if filter_type == "purchase" and row["tx_type"] != "Achat":
                continue
            if filter_type == "sale" and row["tx_type"] != "Vente":
                continue
            if filter_type == "payment" and row["tx_kind"] != "payment":
                continue
            if filter_name and filter_name not in f"{row['partner_name']} {row['designation']}".lower():
                continue
            if filter_date and str(row["tx_date"]) != filter_date:
                continue
            if filter_operation and filter_operation not in str(row["tx_type"]).lower():
                continue
            filtered_rows.append(row)

        return render_template(
            "transactions.html",
            transactions=filtered_rows,
            filter_type=filter_type,
            filter_name=request.args.get("name", ""),
            filter_date=request.args.get("date", ""),
            filter_operation=request.args.get("operation", ""),
        )

    bind_route(app, "/operations", "operations", transactions, ["GET"])
    bind_route(app, "/transactions", "transactions", transactions, ["GET"])
