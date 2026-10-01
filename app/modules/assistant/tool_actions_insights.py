# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("fabouanes.assistant")


async def search_web(query: str) -> Dict[str, Any]:
    from app.core.perf_cache import async_cached_result

    async def builder():
        import html
        import re
        import urllib.parse

        import httpx

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=12.0)
                if res.status_code != 200:
                    return {"error": f"DuckDuckGo a renvoyé le statut HTTP {res.status_code}"}

                parts = res.text.split('<div class="result results_links results_links_deep web-result ')
                results = []

                for block in parts[1:7]:  # Limiter aux 6 premiers résultats
                    title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                    snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</', block, re.DOTALL)

                    if title_match:
                        raw_url = title_match.group(1)
                        raw_title = title_match.group(2)

                        url_clean = raw_url
                        if "uddg=" in raw_url:
                            try:
                                parsed = urllib.parse.urlparse(raw_url)
                                queries = urllib.parse.parse_qs(parsed.query)
                                if "uddg" in queries:
                                    url_clean = queries["uddg"][0]
                            except Exception:
                                pass
                        elif url_clean.startswith("//"):
                            url_clean = "https:" + url_clean

                        title = re.sub(r"<[^>]*>", "", raw_title)
                        title = html.unescape(title).strip()

                        snippet = ""
                        if snippet_match:
                            raw_snippet = snippet_match.group(1)
                            snippet = re.sub(r"<[^>]*>", "", raw_snippet)
                            snippet = html.unescape(snippet).strip()

                        results.append({"title": title, "url": url_clean, "snippet": snippet})
                return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    return await async_cached_result(("assistant", "search_web", query), builder, ttl_seconds=300.0)


async def handle_insights(
    func_name: str, func_args: dict, session_maker, user_role: str = "operator"
) -> Dict[str, Any] | None:
    from datetime import date, timedelta
    from sqlalchemy import column, desc, func, literal, select, table, union_all
    from app.core.models import Client, Expense, FinishedProduct, Purchase, RawMaterial, Sale, SaleDocument
    from app.core.perf_cache import async_cached_result

    clients_with_stats = table(
        "clients_with_stats",
        column("name"),
        column("phone"),
        column("current_balance"),
    )

    if func_name == "get_business_insights":
        insight_type = func_args.get("insight_type", "summary").lower()

        async def builder():
            async with session_maker() as session:
                today = date.today()
                month_start = date(today.year, today.month, 1)

                if insight_type == "top_debtors":
                    stmt = (
                        select(
                            clients_with_stats.c.name, clients_with_stats.c.phone, clients_with_stats.c.current_balance
                        )
                        .where(clients_with_stats.c.current_balance > 0)
                        .order_by(desc(clients_with_stats.c.current_balance))
                        .limit(5)
                    )
                    rows = (await session.execute(stmt)).fetchall()
                    return {"top_debtors": [{"name": r[0], "phone": r[1], "debt": float(r[2])} for r in rows]}

                elif insight_type == "monthly_sales_comparison":
                    prev_month_end = month_start - timedelta(days=1)
                    prev_month_start = date(prev_month_end.year, prev_month_end.month, 1)

                    stmt_cur = select(func.coalesce(func.sum(SaleDocument.total), 0)).where(
                        SaleDocument.sale_date >= month_start
                    )
                    stmt_prev = select(func.coalesce(func.sum(SaleDocument.total), 0)).where(
                        SaleDocument.sale_date >= prev_month_start,
                        SaleDocument.sale_date < month_start,
                    )

                    sales_cur = float((await session.execute(stmt_cur)).scalar() or 0)
                    sales_prev = float((await session.execute(stmt_prev)).scalar() or 0)
                    growth = ((sales_cur - sales_prev) / sales_prev * 100) if sales_prev > 0 else 0.0
                    return {
                        "sales_current_month": sales_cur,
                        "sales_previous_month": sales_prev,
                        "growth_rate": round(growth, 2),
                    }

                else:
                    stmt_clients = select(func.count(Client.id))
                    stmt_products = select(func.count(FinishedProduct.id))
                    stmt_month = select(func.coalesce(func.sum(SaleDocument.total), 0)).where(
                        SaleDocument.sale_date >= month_start
                    )

                    clients_count = (await session.execute(stmt_clients)).scalar() or 0
                    products_count = (await session.execute(stmt_products)).scalar() or 0
                    sales_month = float((await session.execute(stmt_month)).scalar() or 0)
                    return {
                        "total_clients": clients_count,
                        "total_products": products_count,
                        "sales_this_month": sales_month,
                    }

        return await async_cached_result(
            ("assistant", "get_business_insights", insight_type), builder, ttl_seconds=60.0
        )

    elif func_name == "explain_profit_decrease":
        period_days = int(func_args.get("period_days", 30))
        async with session_maker() as session:
            today = date.today()
            cur_start = today - timedelta(days=period_days)
            prev_start = today - timedelta(days=period_days * 2)

            stmt_s_cur = select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.sale_date >= cur_start)
            stmt_s_prev = select(func.coalesce(func.sum(Sale.total), 0)).where(
                Sale.sale_date >= prev_start, Sale.sale_date < cur_start
            )

            stmt_p_cur = select(func.coalesce(func.sum(Sale.profit_amount), 0)).where(Sale.sale_date >= cur_start)
            stmt_p_prev = select(func.coalesce(func.sum(Sale.profit_amount), 0)).where(
                Sale.sale_date >= prev_start, Sale.sale_date < cur_start
            )

            stmt_pur_cur = select(func.coalesce(func.sum(Purchase.total), 0)).where(Purchase.purchase_date >= cur_start)
            stmt_pur_prev = select(func.coalesce(func.sum(Purchase.total), 0)).where(
                Purchase.purchase_date >= prev_start, Purchase.purchase_date < cur_start
            )

            stmt_exp_cur = select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.date >= cur_start)
            stmt_exp_prev = select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.date >= prev_start, Expense.date < cur_start
            )

            sales_cur = float((await session.execute(stmt_s_cur)).scalar() or 0)
            sales_prev = float((await session.execute(stmt_s_prev)).scalar() or 0)

            profit_cur = float((await session.execute(stmt_p_cur)).scalar() or 0)
            profit_prev = float((await session.execute(stmt_p_prev)).scalar() or 0)

            purchases_cur = float((await session.execute(stmt_pur_cur)).scalar() or 0)
            purchases_prev = float((await session.execute(stmt_pur_prev)).scalar() or 0)

            expenses_cur = float((await session.execute(stmt_exp_cur)).scalar() or 0)
            expenses_prev = float((await session.execute(stmt_exp_prev)).scalar() or 0)

            sales_var = round(((sales_cur - sales_prev) / sales_prev * 100), 2) if sales_prev > 0 else 0.0
            profit_var = round(((profit_cur - profit_prev) / profit_prev * 100), 2) if profit_prev > 0 else 0.0
            purchases_var = (
                round(((purchases_cur - purchases_prev) / purchases_prev * 100), 2) if purchases_prev > 0 else 0.0
            )
            expenses_var = (
                round(((expenses_cur - expenses_prev) / expenses_prev * 100), 2) if expenses_prev > 0 else 0.0
            )

            return {
                "period_days": period_days,
                "current_period": {
                    "sales": sales_cur,
                    "profit": profit_cur,
                    "purchases": purchases_cur,
                    "expenses": expenses_cur,
                },
                "previous_period": {
                    "sales": sales_prev,
                    "profit": profit_prev,
                    "purchases": purchases_prev,
                    "expenses": expenses_prev,
                },
                "variations_percent": {
                    "sales_change": sales_var,
                    "profit_change": profit_var,
                    "purchases_change": purchases_var,
                    "expenses_change": expenses_var,
                },
                "diagnosis": (
                    f"Le bénéfice a varié de {profit_var}%. "
                    + (
                        f"La baisse s'explique par la hausse des dépenses (+{expenses_var}%) ou des coûts d'achats (+{purchases_var}%)."
                        if profit_var < 0
                        else "Le bénéfice est en progression."
                    )
                ),
            }

    elif func_name == "predict_business_trends":
        async with session_maker() as session:
            stmt_fp = select(
                FinishedProduct.name.label("name"),
                FinishedProduct.stock_qty.label("stock_qty"),
                FinishedProduct.alert_threshold.label("alert_threshold"),
                literal("Produit fini").label("item_type"),
            ).where(FinishedProduct.stock_qty <= FinishedProduct.alert_threshold, FinishedProduct.alert_threshold > 0)

            stmt_rm = select(
                RawMaterial.name.label("name"),
                RawMaterial.stock_qty.label("stock_qty"),
                RawMaterial.alert_threshold.label("alert_threshold"),
                literal("Matière première").label("item_type"),
            ).where(RawMaterial.stock_qty <= RawMaterial.alert_threshold, RawMaterial.alert_threshold > 0)

            subq_stock = union_all(stmt_fp, stmt_rm).subquery()
            stock_alerts = (
                await session.execute(
                    select(
                        subq_stock.c.name, subq_stock.c.stock_qty, subq_stock.c.alert_threshold, subq_stock.c.item_type
                    )
                    .order_by(subq_stock.c.stock_qty.asc())
                    .limit(5)
                )
            ).fetchall()

            d_30 = date.today() - timedelta(days=30)
            stmt_avg = select(func.coalesce(func.sum(Sale.total), 0) / 30.0).where(Sale.sale_date >= d_30)
            daily_sales_avg = float((await session.execute(stmt_avg)).scalar() or 0)
            forecast_sales_30d = round(daily_sales_avg * 30, 2)

            stmt_rec = select(func.coalesce(func.sum(clients_with_stats.c.current_balance), 0)).where(
                clients_with_stats.c.current_balance > 0
            )
            pending_receivables = float((await session.execute(stmt_rec)).scalar() or 0)

            return {
                "forecast_sales_next_30_days": forecast_sales_30d,
                "daily_sales_velocity": round(daily_sales_avg, 2),
                "imminent_stock_runouts": [
                    {"name": r[0], "stock": float(r[1]), "threshold": float(r[2]), "type": r[3]} for r in stock_alerts
                ],
                "expected_debt_collections": pending_receivables,
                "summary": f"Prévision Ventes 30j: {forecast_sales_30d:,.0f} DA | {len(stock_alerts)} articles à réapprovisionner d'urgence.",
            }

    elif func_name == "detect_anomalies":
        async with session_maker() as session:
            d_30 = date.today() - timedelta(days=30)
            stmt_dups = (
                select(
                    func.coalesce(Client.name, "Client Divers").label("client_name"),
                    Sale.total,
                    func.count().label("count"),
                )
                .join(Client, Sale.client_id == Client.id, isouter=True)
                .where(Sale.sale_date >= d_30)
                .group_by(Client.name, Sale.total)
                .having(func.count() > 1)
                .limit(5)
            )
            duplicates = (await session.execute(stmt_dups)).fetchall()

            avg_exp = float((await session.execute(select(func.coalesce(func.avg(Expense.amount), 0)))).scalar() or 0)
            threshold_amt = avg_exp * 2.5 if avg_exp > 0 else 10000.0

            stmt_high = (
                select(Expense.description, Expense.amount, Expense.date)
                .where(Expense.amount > threshold_amt, Expense.date >= d_30)
                .order_by(desc(Expense.amount))
                .limit(5)
            )
            high_expenses = (await session.execute(stmt_high)).fetchall()

            return {
                "potential_duplicate_sales": [
                    {"client": r[0], "total": float(r[1]), "count": r[2]} for r in duplicates
                ],
                "abnormal_high_expenses": [
                    {"label": r[0], "amount": float(r[1]), "date": str(r[2])} for r in high_expenses
                ],
                "average_expense_benchmark": round(avg_exp, 2),
                "status": "Analyse effectuée avec succès. "
                + (
                    f"{len(duplicates)} doublons potentiels détectés."
                    if duplicates
                    else "Aucune anomalie critique détectée."
                ),
            }

    elif func_name == "get_current_weather":
        location = func_args.get("location", "Paris").strip()
        from app.core.perf_cache import async_cached_result

        async def builder():
            import httpx

            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(f"https://wttr.in/{location}?format=3", timeout=15.0)
                    if res.status_code == 200:
                        return {"weather": res.text.strip()}
                    return {"error": f"Code HTTP {res.status_code} retourné par le service météo."}
            except Exception as e:
                return {"error": str(e)}

        res = await async_cached_result(("assistant", "get_current_weather", location), builder, ttl_seconds=600.0)
        return res

    elif func_name == "search_web":
        query = func_args.get("query", "").strip()
        return await search_web(query)

    return None
