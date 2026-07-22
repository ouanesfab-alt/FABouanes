"""
Sabrina Morning Briefing — Résumé proactif au login.

Génère un briefing matinal automatique avec les KPIs clés de l'entreprise :
alertes stock, ventes de la veille, versements reçus, clients endettés.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from app.core.db_helpers import db_manager

logger = logging.getLogger("fabouanes.assistant.briefing")


def generate_briefing() -> Dict[str, Any]:
    """
    Génère un résumé proactif des données de l'entreprise.
    Retourne un dictionnaire avec les sections du briefing.
    """
    sections = []

    try:
        # 1. Alertes de stock
        stock_alerts = db_manager.query_db("""
            SELECT name, stock_qty, alert_threshold, default_unit, 'Produit fini' AS type
            FROM finished_products WHERE alert_threshold > 0 AND stock_qty <= alert_threshold
            UNION ALL
            SELECT name, stock_qty, alert_threshold, unit, 'Matière première'
            FROM raw_materials WHERE alert_threshold > 0 AND stock_qty <= alert_threshold
            ORDER BY stock_qty ASC
        """)

        if stock_alerts:
            alerts_md = []
            for r in stock_alerts:
                try:
                    row = dict(r)
                    # Normalize field name: raw_materials uses 'unit', finished_products uses 'default_unit'
                    # The UNION aliases it as 'default_unit' — but on fallback we handle both
                    if "default_unit" not in row and "unit" in row:
                        row["default_unit"] = row["unit"]
                except Exception:
                    row = {"name": r[0], "stock_qty": r[1], "alert_threshold": r[2], "default_unit": r[3], "type": r[4]}

                icon = "🔴" if float(row.get("stock_qty", 0)) == 0 else "🟡"
                alerts_md.append(
                    f"{icon} **{row['name']}** ({row['type']}) — "
                    f"Stock: {row.get('stock_qty', 0)} {row.get('default_unit') or row.get('unit', '')} "
                    f"(seuil: {row.get('alert_threshold', 0)})"
                )
            sections.append({
                "title": "⚠️ Alertes de Stock",
                "items": alerts_md,
                "priority": "high"
            })
    except Exception as e:
        logger.error("Briefing stock error: %s", e)

    try:
        # 2. Bilan de la veille
        yesterday_summary = db_manager.query_db("""
            SELECT
                (SELECT COALESCE(SUM(total), 0) FROM sales WHERE sale_date = date('now', '-1 day')) AS ventes_hier,
                (SELECT COALESCE(SUM(total), 0) FROM purchases WHERE purchase_date = date('now', '-1 day')) AS achats_hier,
                (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date = date('now', '-1 day')) AS versements_hier,
                (SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date = date('now', '-1 day')) AS depenses_hier
        """)

        if yesterday_summary:
            try:
                row = dict(yesterday_summary[0])
            except Exception:
                r = yesterday_summary[0]
                row = {"ventes_hier": r[0], "achats_hier": r[1], "versements_hier": r[2], "depenses_hier": r[3]}

            ventes = float(row.get("ventes_hier", 0))
            achats = float(row.get("achats_hier", 0))
            versements = float(row.get("versements_hier", 0))
            depenses = float(row.get("depenses_hier", 0))

            if any([ventes, achats, versements, depenses]):
                items = []
                if ventes > 0:
                    items.append(f"💰 Ventes : **{ventes:,.0f} DA**")
                if achats > 0:
                    items.append(f"📦 Achats : **{achats:,.0f} DA**")
                if versements > 0:
                    items.append(f"💵 Versements reçus : **{versements:,.0f} DA**")
                if depenses > 0:
                    items.append(f"📊 Dépenses : **{depenses:,.0f} DA**")

                sections.append({
                    "title": "📋 Bilan d'hier",
                    "items": items,
                    "priority": "medium"
                })
    except Exception as e:
        logger.error("Briefing yesterday error: %s", e)

    try:
        # 3. Bilan du mois en cours
        month_summary = db_manager.query_db("""
            SELECT
                (SELECT COALESCE(SUM(total), 0) FROM sales WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE)) AS ca_mois,
                (SELECT COALESCE(SUM(profit_amount), 0) FROM sales WHERE sale_date >= DATE_TRUNC('month', CURRENT_DATE)) AS benefice_mois
        """)

        if month_summary:
            try:
                row = dict(month_summary[0])
            except Exception:
                r = month_summary[0]
                row = {"ca_mois": r[0], "benefice_mois": r[1]}

            ca = float(row.get("ca_mois", 0))
            benefice = float(row.get("benefice_mois", 0))

            if ca > 0:
                sections.append({
                    "title": "📈 Ce mois-ci",
                    "items": [
                        f"Chiffre d'affaires : **{ca:,.0f} DA**",
                        f"Bénéfice : **{benefice:,.0f} DA**"
                    ],
                    "priority": "medium"
                })
    except Exception as e:
        logger.error("Briefing month error: %s", e)

    try:
        # 4. Top 3 clients endettés
        top_debtors = db_manager.query_db("""
            SELECT name, current_balance
            FROM clients_with_stats
            WHERE current_balance > 0
            ORDER BY current_balance DESC
            LIMIT 3
        """)

        if top_debtors:
            items = []
            for r in top_debtors:
                try:
                    row = dict(r)
                except Exception:
                    row = {"name": r[0], "current_balance": r[1]}
                items.append(f"👤 {row['name']} — **{float(row['current_balance']):,.0f} DA**")

            sections.append({
                "title": "💳 Principaux débiteurs",
                "items": items,
                "priority": "low"
            })
    except Exception as e:
        logger.error("Briefing debtors error: %s", e)

    # Construire le message Markdown final
    if not sections:
        return {
            "has_briefing": False,
            "markdown": ""
        }

    md_parts = ["☀️ **Bonjour ! Voici votre résumé :**\n"]
    for section in sections:
        md_parts.append(f"### {section['title']}")
        for item in section["items"]:
            md_parts.append(f"- {item}")
        md_parts.append("")  # ligne vide entre sections

    md_parts.append("---\n*Comment puis-je vous aider aujourd'hui ?* 😊")

    return {
        "has_briefing": True,
        "markdown": "\n".join(md_parts),
        "sections_count": len(sections),
        "alert_count": sum(len(s["items"]) for s in sections if s["priority"] == "high")
    }


async def generate_briefing_async() -> Dict[str, Any]:
    """Exécute generate_briefing de manière non-bloquante dans un thread dédié."""
    import asyncio
    return await asyncio.to_thread(generate_briefing)

