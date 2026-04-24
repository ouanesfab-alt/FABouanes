from __future__ import annotations

from fabouanes.fastapi_compat import flash, redirect, render_template, request, url_for

from fabouanes.core.activity import log_activity
from fabouanes.core.db_access import execute_db, query_db
from fabouanes.core.decorators import login_required
from fabouanes.core.storage import backup_database
from fabouanes.routes.route_utils import bind_route


def register_contact_routes(app):
    @login_required
    def suppliers():
        if request.method == "POST":
            supplier_name = request.form["name"].strip()
            execute_db(
                "INSERT INTO suppliers (name, phone, address, notes) VALUES (?, ?, ?, ?)",
                (
                    supplier_name,
                    request.form.get("phone", "").strip(),
                    request.form.get("address", "").strip(),
                    request.form.get("notes", "").strip(),
                ),
            )
            log_activity("create_supplier", "supplier", None, supplier_name)
            backup_database("create_supplier")
            flash("Fournisseur ajouté avec succès.", "success")
            return redirect(url_for("suppliers"))
        return render_template("suppliers.html", suppliers=query_db("SELECT * FROM suppliers ORDER BY name"))

    @login_required
    def new_supplier():
        if request.method == "POST":
            supplier_name = request.form["name"].strip()
            execute_db(
                "INSERT INTO suppliers (name, phone, address, notes) VALUES (?, ?, ?, ?)",
                (
                    supplier_name,
                    request.form.get("phone", "").strip(),
                    request.form.get("address", "").strip(),
                    request.form.get("notes", "").strip(),
                ),
            )
            log_activity("create_supplier", "supplier", None, supplier_name)
            backup_database("create_supplier")
            flash("Fournisseur ajouté avec succès.", "success")
            return redirect(url_for("suppliers"))
        return render_template("supplier_new.html")

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

    @login_required
    def edit_supplier(supplier_id: int):
        supplier = query_db("SELECT * FROM suppliers WHERE id = ?", (supplier_id,), one=True)
        if not supplier:
            flash("Fournisseur introuvable.", "danger")
            return redirect(url_for("suppliers"))
        if request.method == "POST":
            supplier_name = request.form["name"].strip()
            execute_db(
                "UPDATE suppliers SET name=?, phone=?, address=?, notes=? WHERE id=?",
                (
                    supplier_name,
                    request.form.get("phone", "").strip(),
                    request.form.get("address", "").strip(),
                    request.form.get("notes", "").strip(),
                    supplier_id,
                ),
            )
            log_activity("update_supplier", "supplier", supplier_id, supplier_name)
            backup_database("update_supplier")
            flash("Fournisseur modifié.", "success")
            return redirect(url_for("suppliers"))
        return render_template("supplier_edit.html", supplier=supplier)

    @login_required
    def delete_supplier(supplier_id: int):
        execute_db("DELETE FROM suppliers WHERE id=?", (supplier_id,))
        log_activity("delete_supplier", "supplier", supplier_id, "Suppression fournisseur")
        backup_database("delete_supplier")
        flash("Fournisseur supprimé.", "success")
        return redirect(url_for("suppliers"))

    bind_route(app, "/suppliers", "suppliers", suppliers, ["GET", "POST"])
    bind_route(app, "/suppliers/new", "new_supplier", new_supplier, ["GET", "POST"])
    bind_route(app, "/contacts", "contacts", contacts, ["GET"])
    bind_route(app, "/suppliers/<int:supplier_id>", "supplier_detail", supplier_detail, ["GET"])
    bind_route(app, "/suppliers/<int:supplier_id>/edit", "edit_supplier", edit_supplier, ["GET", "POST"])
    bind_route(app, "/suppliers/<int:supplier_id>/delete", "delete_supplier", delete_supplier, ["POST"])
