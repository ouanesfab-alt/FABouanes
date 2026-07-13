# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict

logger = logging.getLogger("fabouanes.assistant")

async def search_web(query: str) -> Dict[str, Any]:
    from app.core.perf_cache import async_cached_result
    async def builder():
        import httpx
        import urllib.parse
        import re
        import html
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
