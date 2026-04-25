from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from fabouanes.core.db_access import query_db
from fabouanes.core.decorators import login_required
from fabouanes.routes.route_utils import bind_route


def register_contact_routes(app):
    @login_required
    def contacts():
        rows = query_db(
            """
            SELECT * FROM (
                SELECT 'Client' AS contact_type, c.id, c.name, c.phone, c.address, c.notes,
                       c.opening_credit
                       + COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id AND s.sale_type = 'credit'), 0)
                       + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id AND rs.sale_type = 'credit'), 0)
                       - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'versement'), 0)
                       + COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'avance'), 0) AS current_balance,
                       COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id), 0)
                       + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id), 0) AS total_amount,
                       COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'versement'), 0) AS total_paid
                FROM clients c
                UNION ALL
                SELECT 'Fournisseur' AS contact_type, s.id, s.name, s.phone, s.address, s.notes,
                       0 AS current_balance,
                       COALESCE((SELECT SUM(total) FROM purchases p WHERE p.supplier_id = s.id), 0) AS total_amount,
                       0 AS total_paid
                FROM suppliers s
            ) x
            ORDER BY contact_type, name
            """
        )
        filter_type = request.args.get("type", "all")
        filter_name = (request.args.get("name") or "").strip().lower()
        filtered_rows = []
        for row in rows:
            if filter_type == "client" and row["contact_type"] != "Client":
                continue
            if filter_type == "supplier" and row["contact_type"] != "Fournisseur":
                continue
            haystack = f"{row['name']} {row['phone'] or ''} {row['address'] or ''}".lower()
            if filter_name and filter_name not in haystack:
                continue
            filtered_rows.append(row)
        return render_template(
            "contacts.html",
            contacts=filtered_rows,
            filter_type=filter_type,
            filter_name=request.args.get("name", ""),
        )

    @login_required
    def supplier_detail(supplier_id: int):
        supplier = query_db("SELECT * FROM suppliers WHERE id = ?", (supplier_id,), one=True)
        if not supplier:
            flash("Fournisseur introuvable.", "danger")
            return redirect(url_for("contacts", type="supplier"))

        purchases_rows = query_db(
            """
            SELECT p.id, p.document_id, p.purchase_date AS event_date, r.name AS designation, p.quantity, r.unit, p.unit_price, p.total, p.notes
            FROM purchases p
            JOIN raw_materials r ON r.id = p.raw_material_id
            WHERE p.supplier_id = ?
            ORDER BY p.purchase_date DESC, p.id DESC
            """,
            (supplier_id,),
        )
        total_amount = sum(float(row["total"]) for row in purchases_rows)
        return render_template("supplier_detail.html", supplier=supplier, purchases=purchases_rows, total_amount=total_amount)

    bind_route(app, "/contacts", "contacts", contacts, ["GET"])
    bind_route(app, "/suppliers/<int:supplier_id>", "supplier_detail", supplier_detail, ["GET"])
