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

                        title = re.sub(r'<[^>]*>', '', raw_title)
                        title = html.unescape(title).strip()

                        snippet = ""
                        if snippet_match:
                            raw_snippet = snippet_match.group(1)
                            snippet = re.sub(r'<[^>]*>', '', raw_snippet)
                            snippet = html.unescape(snippet).strip()

                        results.append({
                            "title": title,
                            "url": url_clean,
                            "snippet": snippet
                        })
                return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    return await async_cached_result(("assistant", "search_web", query), builder, ttl_seconds=300.0)


async def handle_insights(func_name: str, func_args: dict, session_maker, user_role: str = 'operator') -> Dict[str, Any] | None:

    if func_name == "get_business_insights":
            insight_type = func_args.get("insight_type", "summary").lower()
            from app.core.perf_cache import async_cached_result
            async def builder():
                from sqlmodel import text
                async with session_maker() as session:
                    if insight_type == "top_debtors":
                        rows = (await session.execute(text(
                            "SELECT name, phone, current_balance FROM clients_with_stats WHERE current_balance > 0 ORDER BY current_balance DESC LIMIT 5"
                        ))).fetchall()
                        return {"top_debtors": [{"name": r[0], "phone": r[1], "debt": float(r[2])} for r in rows]}
                    elif insight_type == "monthly_sales_comparison":
                        sales_cur = (await session.execute(text(
                            "SELECT COALESCE(SUM(total), 0) FROM sale_documents WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE)"
                        ))).scalar()
                        sales_prev = (await session.execute(text(
                            "SELECT COALESCE(SUM(total), 0) FROM sale_documents WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND sale_date < DATE_TRUNC('month', CURRENT_DATE)"
                        ))).scalar()
                        sales_cur = float(sales_cur)
                        sales_prev = float(sales_prev)
                        growth = ((sales_cur - sales_prev) / sales_prev * 100) if sales_prev > 0 else 0.0
                        return {
                            "sales_current_month": sales_cur,
                            "sales_previous_month": sales_prev,
                            "growth_rate": round(growth, 2)
                        }
                    else:
                        clients_count = (await session.execute(text("SELECT COUNT(*) FROM clients"))).scalar()
                        products_count = (await session.execute(text("SELECT COUNT(*) FROM finished_products"))).scalar()
                        sales_month = (await session.execute(text("SELECT COALESCE(SUM(total), 0) FROM sale_documents WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE)"))).scalar()
                        return {
                            "total_clients": clients_count,
                            "total_products": products_count,
                            "sales_this_month": float(sales_month)
                        }
            res = await async_cached_result(("assistant", "get_business_insights", insight_type), builder, ttl_seconds=60.0)
            return res

    elif func_name == "explain_profit_decrease":
        period_days = int(func_args.get("period_days", 30))
        from sqlmodel import text
        async with session_maker() as session:
            sales_cur = float((await session.execute(text(
                "SELECT COALESCE(SUM(total), 0) FROM sales WHERE sale_date >= CURRENT_DATE - INTERVAL '%d days'" % period_days
            ))).scalar() or 0)
            sales_prev = float((await session.execute(text(
                "SELECT COALESCE(SUM(total), 0) FROM sales WHERE sale_date >= CURRENT_DATE - INTERVAL '%d days' AND sale_date < CURRENT_DATE - INTERVAL '%d days'" % (period_days * 2, period_days)
            ))).scalar() or 0)

            profit_cur = float((await session.execute(text(
                "SELECT COALESCE(SUM(profit_amount), 0) FROM sales WHERE sale_date >= CURRENT_DATE - INTERVAL '%d days'" % period_days
            ))).scalar() or 0)
            profit_prev = float((await session.execute(text(
                "SELECT COALESCE(SUM(profit_amount), 0) FROM sales WHERE sale_date >= CURRENT_DATE - INTERVAL '%d days' AND sale_date < CURRENT_DATE - INTERVAL '%d days'" % (period_days * 2, period_days)
            ))).scalar() or 0)

            purchases_cur = float((await session.execute(text(
                "SELECT COALESCE(SUM(total), 0) FROM purchases WHERE purchase_date >= CURRENT_DATE - INTERVAL '%d days'" % period_days
            ))).scalar() or 0)
            purchases_prev = float((await session.execute(text(
                "SELECT COALESCE(SUM(total), 0) FROM purchases WHERE purchase_date >= CURRENT_DATE - INTERVAL '%d days' AND purchase_date < CURRENT_DATE - INTERVAL '%d days'" % (period_days * 2, period_days)
            ))).scalar() or 0)

            expenses_cur = float((await session.execute(text(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date >= CURRENT_DATE - INTERVAL '%d days'" % period_days
            ))).scalar() or 0)
            expenses_prev = float((await session.execute(text(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date >= CURRENT_DATE - INTERVAL '%d days' AND date < CURRENT_DATE - INTERVAL '%d days'" % (period_days * 2, period_days)
            ))).scalar() or 0)

            sales_var = round(((sales_cur - sales_prev) / sales_prev * 100), 2) if sales_prev > 0 else 0.0
            profit_var = round(((profit_cur - profit_prev) / profit_prev * 100), 2) if profit_prev > 0 else 0.0
            purchases_var = round(((purchases_cur - purchases_prev) / purchases_prev * 100), 2) if purchases_prev > 0 else 0.0
            expenses_var = round(((expenses_cur - expenses_prev) / expenses_prev * 100), 2) if expenses_prev > 0 else 0.0

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
                    f"Le bénéfice a varié de {profit_var}%. " +
                    (f"La baisse s'explique par la hausse des dépenses (+{expenses_var}%) ou des coûts d'achats (+{purchases_var}%)." if profit_var < 0 else "Le bénéfice est en progression.")
                )
            }

    elif func_name == "predict_business_trends":
        from sqlmodel import text
        async with session_maker() as session:
            stock_alerts = (await session.execute(text("""
                SELECT name, stock_qty, alert_threshold, 'Produit fini' AS type FROM finished_products WHERE stock_qty <= alert_threshold AND alert_threshold > 0
                UNION ALL
                SELECT name, stock_qty, alert_threshold, 'Matière première' FROM raw_materials WHERE stock_qty <= alert_threshold AND alert_threshold > 0
                ORDER BY stock_qty ASC LIMIT 5
            """))).fetchall()

            daily_sales_avg = float((await session.execute(text(
                "SELECT COALESCE(SUM(total), 0) / 30.0 FROM sales WHERE sale_date >= CURRENT_DATE - INTERVAL '30 days'"
            ))).scalar() or 0)
            forecast_sales_30d = round(daily_sales_avg * 30, 2)

            pending_receivables = float((await session.execute(text(
                "SELECT COALESCE(SUM(current_balance), 0) FROM clients_with_stats WHERE current_balance > 0"
            ))).scalar() or 0)

            return {
                "forecast_sales_next_30_days": forecast_sales_30d,
                "daily_sales_velocity": round(daily_sales_avg, 2),
                "imminent_stock_runouts": [{"name": r[0], "stock": float(r[1]), "threshold": float(r[2]), "type": r[3]} for r in stock_alerts],
                "expected_debt_collections": pending_receivables,
                "summary": f"Prévision Ventes 30j: {forecast_sales_30d:,.0f} DA | {len(stock_alerts)} articles à réapprovisionner d'urgence."
            }

    elif func_name == "detect_anomalies":
        from sqlmodel import text
        async with session_maker() as session:
            duplicates = (await session.execute(text("""
                SELECT client_name, total, COUNT(*) FROM sales
                WHERE sale_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY client_name, total HAVING COUNT(*) > 1 LIMIT 5
            """))).fetchall()

            avg_exp = float((await session.execute(text("SELECT COALESCE(AVG(amount), 0) FROM expenses"))).scalar() or 0)
            high_expenses = (await session.execute(text("""
                SELECT label, amount, date FROM expenses WHERE amount > %s AND date >= CURRENT_DATE - INTERVAL '30 days' ORDER BY amount DESC LIMIT 5
            """ % (avg_exp * 2.5 if avg_exp > 0 else 10000)))).fetchall()

            return {
                "potential_duplicate_sales": [{"client": r[0], "total": float(r[1]), "count": r[2]} for r in duplicates],
                "abnormal_high_expenses": [{"label": r[0], "amount": float(r[1]), "date": str(r[2])} for r in high_expenses],
                "average_expense_benchmark": round(avg_exp, 2),
                "status": "Analyse effectuée avec succès. " + (f"{len(duplicates)} doublons potentiels détectés." if duplicates else "Aucune anomalie critique détectée.")
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
