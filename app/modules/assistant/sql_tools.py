"""
sql_tools.py — Outils SQL de Sabrina (IA).

CONFORMITÉ RÈGLE 3 (GEMINI.md) :
Ce module est STRICTEMENT RÉSERVÉ au SELECT en lecture seule.
Toute écriture doit impérativement passer par les services métiers via le Unit of Work (uow.py).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict

import sqlglot

from app.core.database import db_manager
from app.modules.assistant.sql_guard import validate_readonly_sql as guard_readonly_sql

logger = logging.getLogger("fabouanes.assistant.sql_tools")


def serialize_for_json(obj: Any) -> Any:
    """Convertit récursivement les Decimal, date et datetime en types JSON sérialisables."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(x) for x in obj]
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def execute_readonly_sql(query: str) -> Dict[str, Any]:
    """Exécute une requête SQL SELECT en lecture seule et retourne le résultat."""
    validation = guard_readonly_sql(query)
    if not validation.ok:
        return {"error": validation.error}

    sql_to_run = validation.sql_to_run or query

    try:
        from app.core.database import is_sqlite

        # SET LOCAL must run inside the same transaction as the query to have effect
        with db_manager.db_transaction() as conn:
            if is_sqlite():
                try:
                    conn.execute("PRAGMA busy_timeout = 3000")
                    conn.execute("PRAGMA query_only = ON")
                except Exception as pe:
                    logger.debug("SQLite pragma query_only error: %s", pe)
            else:
                conn.execute("SET LOCAL statement_timeout = '3000'")
                conn.execute("SET TRANSACTION READ ONLY")
            rows = conn.execute(sql_to_run).fetchall()
        return {"rows": serialize_for_json([dict(r) for r in rows])}
    except Exception as e:
        logger.error("execute_readonly_sql error for query %s: %s", sql_to_run, e, exc_info=True)
        err_msg = str(e)
        if "statement timeout" in err_msg.lower() or "57014" in err_msg or "timeout" in err_msg.lower():
            return {"error": "⚠️ La requête a pris trop de temps (>3s / timeout). Essayez d'ajouter des filtres WHERE ou LIMIT."}
        return {"error": f"Erreur SQL : {err_msg}"}


def explain_sql_query(query: str) -> str:
    """Generates a clear natural language breakdown of a SQL query for transparency."""
    if not query:
        return ""
    q = query.strip()
    try:
        stmts = sqlglot.parse(q, read="postgres")
        if not stmts or not stmts[0]:
            return f"```sql\n{q}\n```"
        stmt = stmts[0]
        table_names = [t.name for t in stmt.find_all(sqlglot.exp.Table)]
        tables_str = ", ".join(dict.fromkeys(table_names)) or "base de données"

        if isinstance(stmt, sqlglot.exp.Select):
            return f"🔍 **Lecture SQL** sur {tables_str}\n```sql\n{q}\n```"
        elif isinstance(stmt, sqlglot.exp.Insert):
            return f"➕ **Ajout SQL** dans {tables_str}\n```sql\n{q}\n```"
        elif isinstance(stmt, sqlglot.exp.Update):
            return f"✏️ **Mise à jour SQL** sur {tables_str}\n```sql\n{q}\n```"
        elif isinstance(stmt, sqlglot.exp.Delete):
            return f"🗑️ **Suppression SQL** sur {tables_str}\n```sql\n{q}\n```"
        return f"```sql\n{q}\n```"
    except Exception:
        return f"```sql\n{q}\n```"

