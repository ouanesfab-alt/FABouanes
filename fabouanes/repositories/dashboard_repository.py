from __future__ import annotations

from datetime import date, timedelta

from fabouanes.core.db_access import query_db
from fabouanes.core.perf_cache import cached_result


def get_dashboard_snapshot(target_date: str | None = None) -> dict:
    resolved_date = target_date or date.today().isoformat()
    return cached_result(
        ("dashboard_snapshot", resolved_date),
        lambda: _build_dashboard_snapshot(resolved_date),
        ttl_seconds=6.0,
    )


def get_kpis_for_date(target_date: str) -> dict[str, float | str]:
    return cached_result(
        ("dashboard_kpis", target_date),
        lambda: _build_kpis_for_date(target_date),
        ttl_seconds=10.0,
    )


def _build_dashboard_snapshot(today: str) -> dict:
    target_day = date.fromisoformat(today)
    cutoff_30d = (target_day - timedelta(days=30)).isoformat()
    week_iso = (target_day - timedelta(days=7)).isoformat()

    summary = query_db(
        """
        SELECT
            COALESCE((SELECT SUM(total) FROM sales WHERE sale_date = ?), 0)
            + COALESCE((SELECT SUM(total) FROM raw_sales WHERE sale_date = ?), 0) AS sales_today,
            COALESCE((SELECT SUM(total) FROM sales WHERE sale_date = ?), 0)
            + COALESCE((SELECT SUM(total) FROM raw_sales WHERE sale_date = ?), 0) AS sales_week_ago,
            COALESCE((SELECT SUM(amount) FROM payments WHERE payment_date = ?), 0) AS cash_today,
            COALESCE((SELECT SUM(opening_credit) FROM clients), 0)
            + COALESCE((SELECT SUM(total) FROM sales WHERE sale_type = 'credit'), 0)
            + COALESCE((SELECT SUM(total) FROM raw_sales WHERE sale_type = 'credit'), 0)
            - COALESCE((SELECT SUM(amount) FROM payments WHERE payment_type = 'versement'), 0)
            + COALESCE((SELECT SUM(amount) FROM payments WHERE payment_type = 'avance'), 0) AS total_receivables,
            COALESCE((SELECT SUM(profit_amount) FROM sales WHERE sale_date = ?), 0)
            + COALESCE((SELECT SUM(profit_amount) FROM raw_sales WHERE sale_date = ?), 0) AS profit_today,
            COALESCE((SELECT SUM(profit_amount) FROM sales), 0)
            + COALESCE((SELECT SUM(profit_amount) FROM raw_sales), 0) AS total_profit,
            COALESCE((SELECT SUM(total) FROM sales), 0)
            + COALESCE((SELECT SUM(total) FROM raw_sales), 0) AS revenue,
            COALESCE((SELECT SUM(quantity * cost_price_snapshot) FROM sales), 0)
            + COALESCE((
                SELECT SUM(
                    (CASE
                        WHEN lower(unit) = 'sac' THEN quantity * 50
                        WHEN lower(unit) IN ('qt', 'quintal') THEN quantity * 100
                        ELSE quantity
                    END) * cost_price_snapshot
                )
                FROM raw_sales
            ), 0) AS cost_of_goods,
            COALESCE((SELECT SUM(profit_amount) FROM sales), 0)
            + COALESCE((SELECT SUM(profit_amount) FROM raw_sales), 0) AS gross_profit
        """,
        (today, today, week_iso, week_iso, today, today, today),
        one=True,
    )

    low_stock = query_db("SELECT * FROM raw_materials WHERE stock_qty <= alert_threshold ORDER BY stock_qty ASC")
    recent_sales = query_db(
        """
        SELECT * FROM (
            SELECT s.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                   s.total, s.balance_due, s.profit_amount, 'Produit fini' AS source
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            UNION ALL
            SELECT rs.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                   rs.total, rs.balance_due, rs.profit_amount, 'Matiere premiere' AS source
            FROM raw_sales rs
            LEFT JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
        ) x
        ORDER BY sale_date DESC LIMIT 10
        """
    )
    counts = query_db(
        """
        SELECT
            (SELECT COUNT(*) FROM clients) AS clients,
            (SELECT COUNT(*) FROM suppliers) AS suppliers,
            (SELECT COUNT(*) FROM raw_materials) AS raw_materials,
            (SELECT COUNT(*) FROM finished_products) AS products
        """,
        one=True,
    )
    sales_summary = query_db(
        """
        SELECT sale_date,
               SUM(nb_sales) AS nb_sales,
               SUM(total_sales) AS total_sales,
               SUM(total_paid) AS total_paid,
               SUM(total_due) AS total_due,
               SUM(total_profit) AS total_profit
        FROM (
            SELECT sale_date, COUNT(*) AS nb_sales, SUM(total) AS total_sales, SUM(amount_paid) AS total_paid,
                   SUM(balance_due) AS total_due, SUM(profit_amount) AS total_profit
            FROM sales GROUP BY sale_date
            UNION ALL
            SELECT sale_date, COUNT(*) AS nb_sales, SUM(total) AS total_sales, SUM(amount_paid) AS total_paid,
                   SUM(balance_due) AS total_due, SUM(profit_amount) AS total_profit
            FROM raw_sales GROUP BY sale_date
        ) x
        GROUP BY sale_date
        ORDER BY sale_date DESC LIMIT 15
        """
    )
    stock_materials_raw = query_db(
        """
        WITH consumed AS (
            SELECT raw_material_id, SUM(qty) AS consumed_30d
            FROM (
                SELECT raw_material_id,
                       CASE
                           WHEN lower(unit) = 'sac' THEN quantity * 50
                           WHEN lower(unit) IN ('qt', 'quintal') THEN quantity * 100
                           ELSE quantity
                       END AS qty
                FROM raw_sales
                WHERE sale_date >= ?
                UNION ALL
                SELECT pbi.raw_material_id, pbi.quantity AS qty
                FROM production_batch_items pbi
                JOIN production_batches pb ON pb.id = pbi.batch_id
                WHERE pb.production_date >= ?
            ) source
            GROUP BY raw_material_id
        )
        SELECT rm.*, COALESCE(c.consumed_30d, 0) AS consumed_30d
        FROM raw_materials rm
        LEFT JOIN consumed c ON c.raw_material_id = rm.id
        ORDER BY rm.name
        LIMIT 15
        """,
        (cutoff_30d, cutoff_30d),
    )
    stock_materials = []
    for material in stock_materials_raw:
        row = dict(material)
        daily = float(row.get("consumed_30d") or 0) / 30.0
        row["days_left"] = int(round(float(row["stock_qty"]) / daily)) if daily > 0.01 else None
        stock_materials.append(row)
    stock_products = query_db("SELECT * FROM finished_products ORDER BY name LIMIT 10")

    today_value = float(summary["sales_today"] if summary else 0.0)
    week_value = float(summary["sales_week_ago"] if summary else 0.0)
    sales_delta_pct = round((today_value - week_value) / week_value * 100, 1) if week_value > 0 else None

    debt_by_client = query_db(
        """
        WITH finished_totals AS (
            SELECT client_id, SUM(total) AS credit_total
            FROM sales
            WHERE client_id IS NOT NULL AND sale_type = 'credit'
            GROUP BY client_id
        ),
        raw_totals AS (
            SELECT client_id, SUM(total) AS credit_total
            FROM raw_sales
            WHERE client_id IS NOT NULL AND sale_type = 'credit'
            GROUP BY client_id
        ),
        payment_totals AS (
            SELECT client_id,
                   SUM(CASE WHEN payment_type = 'versement' THEN amount ELSE 0 END) AS versements,
                   SUM(CASE WHEN payment_type = 'avance' THEN amount ELSE 0 END) AS avances
            FROM payments
            GROUP BY client_id
        )
        SELECT * FROM (
            SELECT c.id, c.name,
                   c.opening_credit
                   + COALESCE(ft.credit_total, 0)
                   + COALESCE(rt.credit_total, 0)
                   - COALESCE(pt.versements, 0)
                   + COALESCE(pt.avances, 0) AS balance
            FROM clients c
            LEFT JOIN finished_totals ft ON ft.client_id = c.id
            LEFT JOIN raw_totals rt ON rt.client_id = c.id
            LEFT JOIN payment_totals pt ON pt.client_id = c.id
        ) x
        WHERE balance > 0
        ORDER BY balance DESC
        LIMIT 10
        """
    )
    production_history = query_db(
        """
        SELECT pb.production_date, fp.name AS product_name, pb.output_quantity, pb.production_cost, pb.unit_cost
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
        ORDER BY pb.id DESC
        LIMIT 10
        """
    )
    return {
        "today": today,
        "sales_today": summary["sales_today"],
        "cash_today": summary["cash_today"],
        "total_receivables": summary["total_receivables"],
        "profit_today": summary["profit_today"],
        "total_profit": summary["total_profit"],
        "low_stock": low_stock,
        "recent_sales": recent_sales,
        "counts": dict(counts or {}),
        "sales_summary": sales_summary,
        "stock_materials": stock_materials,
        "stock_products": stock_products,
        "sales_delta_pct": sales_delta_pct,
        "profit_stats": {
            "revenue": summary["revenue"],
            "cost_of_goods": summary["cost_of_goods"],
            "gross_profit": summary["gross_profit"],
        },
        "debt_by_client": debt_by_client,
        "production_history": production_history,
    }


def _build_kpis_for_date(target_date: str) -> dict[str, float | str]:
    row = query_db(
        """
        SELECT
            COALESCE((SELECT SUM(total) FROM sales WHERE sale_date = ?), 0)
            + COALESCE((SELECT SUM(total) FROM raw_sales WHERE sale_date = ?), 0) AS sales,
            COALESCE((SELECT SUM(amount) FROM payments WHERE payment_date = ?), 0) AS cash,
            COALESCE((SELECT SUM(profit_amount) FROM sales WHERE sale_date = ?), 0)
            + COALESCE((SELECT SUM(profit_amount) FROM raw_sales WHERE sale_date = ?), 0) AS profit,
            COALESCE((SELECT SUM(opening_credit) FROM clients), 0)
            + COALESCE((SELECT SUM(total) FROM sales WHERE sale_type = 'credit' AND sale_date <= ?), 0)
            + COALESCE((SELECT SUM(total) FROM raw_sales WHERE sale_type = 'credit' AND sale_date <= ?), 0)
            - COALESCE((SELECT SUM(amount) FROM payments WHERE payment_type = 'versement' AND payment_date <= ?), 0)
            + COALESCE((SELECT SUM(amount) FROM payments WHERE payment_type = 'avance' AND payment_date <= ?), 0) AS receivables
        """,
        (
            target_date,
            target_date,
            target_date,
            target_date,
            target_date,
            target_date,
            target_date,
            target_date,
            target_date,
        ),
        one=True,
    )
    return {
        "date": target_date,
        "sales": float(row["sales"] if row else 0),
        "cash": float(row["cash"] if row else 0),
        "profit": float(row["profit"] if row else 0),
        "receivables": float(row["receivables"] if row else 0),
    }
