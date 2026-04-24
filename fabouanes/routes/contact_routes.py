from __future__ import annotations

from fabouanes.fastapi_compat import flash, redirect, render_template, request, url_for

from fabouanes.core.activity import log_activity
from fabouanes.core.db_access import execute_db, paged_query, query_db
from fabouanes.core.decorators import login_required
from fabouanes.core.pagination import request_pagination
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
        page, page_size = request_pagination()
        suppliers_rows, pagination = paged_query("SELECT * FROM suppliers ORDER BY name", page=page, page_size=page_size)
        return render_template("suppliers.html", suppliers=suppliers_rows, suppliers_pagination=pagination)

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
        filter_type = request.args.get("type", "all")
        filter_name = (request.args.get("name") or "").strip()
        page, page_size = request_pagination()

        base_query = """
            WITH sales_totals AS (
                SELECT
                    client_id,
                    COALESCE(SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END), 0) AS credit_total,
                    COALESCE(SUM(total), 0) AS total_sales
                FROM sales
                GROUP BY client_id
            ),
            raw_sales_totals AS (
                SELECT
                    client_id,
                    COALESCE(SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END), 0) AS credit_total,
                    COALESCE(SUM(total), 0) AS total_sales
                FROM raw_sales
                GROUP BY client_id
            ),
            payment_totals AS (
                SELECT
                    client_id,
                    COALESCE(SUM(CASE WHEN payment_type = 'versement' THEN amount ELSE 0 END), 0) AS total_paid,
                    COALESCE(SUM(CASE WHEN payment_type = 'avance' THEN amount ELSE 0 END), 0) AS total_advance
                FROM payments
                GROUP BY client_id
            ),
            supplier_totals AS (
                SELECT supplier_id, COALESCE(SUM(total), 0) AS total_amount
                FROM purchases
                GROUP BY supplier_id
            )
            SELECT * FROM (
                SELECT
                    'Client' AS contact_type,
                    c.id,
                    c.name,
                    c.phone,
                    c.address,
                    c.notes,
                    c.opening_credit
                        + COALESCE(st.credit_total, 0)
                        + COALESCE(rst.credit_total, 0)
                        - COALESCE(pt.total_paid, 0)
                        + COALESCE(pt.total_advance, 0) AS current_balance,
                    COALESCE(st.total_sales, 0) + COALESCE(rst.total_sales, 0) AS total_amount,
                    COALESCE(pt.total_paid, 0) AS total_paid
                FROM clients c
                LEFT JOIN sales_totals st ON st.client_id = c.id
                LEFT JOIN raw_sales_totals rst ON rst.client_id = c.id
                LEFT JOIN payment_totals pt ON pt.client_id = c.id

                UNION ALL

                SELECT
                    'Fournisseur' AS contact_type,
                    s.id,
                    s.name,
                    s.phone,
                    s.address,
                    s.notes,
                    0 AS current_balance,
                    COALESCE(st.total_amount, 0) AS total_amount,
                    0 AS total_paid
                FROM suppliers s
                LEFT JOIN supplier_totals st ON st.supplier_id = s.id
            ) x
        """

        where: list[str] = []
        params: list[object] = []
        if filter_type == "client":
            where.append("contact_type = ?")
            params.append("Client")
        elif filter_type == "supplier":
            where.append("contact_type = ?")
            params.append("Fournisseur")
        if filter_name:
            where.append("(LOWER(COALESCE(name, '')) LIKE LOWER(?) OR LOWER(COALESCE(phone, '')) LIKE LOWER(?) OR LOWER(COALESCE(address, '')) LIKE LOWER(?))")
            like_value = f"%{filter_name}%"
            params.extend([like_value, like_value, like_value])

        filtered_query = base_query
        if where:
            filtered_query += " WHERE " + " AND ".join(where)
        final_query = filtered_query + " ORDER BY contact_type, name"
        rows, pagination = paged_query(
            final_query,
            tuple(params),
            page=page,
            page_size=page_size,
            count_query=f"SELECT COUNT(*) AS c FROM ({filtered_query}) contacts_src",
            count_params=tuple(params),
        )
        return render_template(
            "contacts.html",
            contacts=rows,
            contacts_pagination=pagination,
            filter_type=filter_type,
            filter_name=filter_name,
        )

    @login_required
    def supplier_detail(supplier_id: int):
        supplier = query_db("SELECT * FROM suppliers WHERE id = ?", (supplier_id,), one=True)
        if not supplier:
            flash("Fournisseur introuvable.", "danger")
            return redirect(url_for("contacts", type="supplier"))

        page, page_size = request_pagination()
        purchases_query = """
            SELECT p.id, p.document_id, p.purchase_date AS event_date, r.name AS designation, p.quantity, r.unit, p.unit_price, p.total, p.notes
            FROM purchases p
            JOIN raw_materials r ON r.id = p.raw_material_id
            WHERE p.supplier_id = ?
            ORDER BY p.purchase_date DESC, p.id DESC
        """
        purchases_rows, pagination = paged_query(
            purchases_query,
            (supplier_id,),
            page=page,
            page_size=page_size,
        )
        total_row = query_db("SELECT COALESCE(SUM(total), 0) AS amount FROM purchases WHERE supplier_id = ?", (supplier_id,), one=True)
        total_amount = float((total_row["amount"] if total_row else 0) or 0)
        return render_template(
            "supplier_detail.html",
            supplier=supplier,
            purchases=purchases_rows,
            purchases_pagination=pagination,
            total_amount=total_amount,
        )

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
