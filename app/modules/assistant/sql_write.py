"""
sql_write.py — Exécution d'écritures SQL directes et simulations pour Sabrina (IA).

ATTENTION / RÈGLE D'ARCHITECTURE :
Ce module est réservé aux opérations exceptionnelles nécessitant des requêtes d'écriture directes.
Toute écriture standard (ventes, achats, paiements, stock, utilisateurs) DOIT impérativement
passer par les services de domaine canoniques via le Unit of Work (uow.py).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import sqlglot

from app.core.database import db_manager
from app.modules.assistant.sql_guard import validate_write_sql as guard_write_sql
from app.modules.assistant.sql_tools import serialize_for_json

logger = logging.getLogger("fabouanes.assistant.sql_write")


class DryRunRollback(Exception):
    def __init__(self, data):
        self.data = data


def dry_run_sql(query: str) -> str:
    """Simule une requête SQL d'écriture dans une transaction temporaire puis effectue un rollback."""
    validation = guard_write_sql(query)
    if not validation.ok:
        return f"⚠️ Requête SQL refusée : {validation.error}"

    query_to_run = validation.sql_to_run or query
    try:
        stmts = validation.statements or sqlglot.parse(query_to_run, read="postgres")
        if not stmts:
            return "⚠️ Requête SQL invalide."
        stmt = stmts[0]
        table_names = [t.name.lower() for t in stmt.find_all(sqlglot.exp.Table)]

        try:
            from app.core.database import is_sqlite

            with db_manager.db_transaction() as conn:
                # Limiter le temps d'exécution des requêtes IA à 4s (strict 3-5s)
                if is_sqlite():
                    try:
                        conn.execute("PRAGMA busy_timeout = 4000")
                    except Exception:
                        pass
                else:
                    conn.execute("SET LOCAL statement_timeout = '4000'")
                # Récupérer les soldes clients avant
                client_balances_before = {}
                if "clients" in table_names:
                    rows = conn.execute("SELECT id, name, current_balance FROM clients_with_stats").fetchall()
                    client_balances_before = {r[0]: (r[1], r[2]) for r in rows}

                cur = conn.execute(query_to_run)
                rowcount = getattr(cur, "rowcount", None)
                inserted_id = None
                try:
                    row = cur.fetchone()
                    if row:
                        if isinstance(row, dict):
                            inserted_id = row.get("id")
                        elif isinstance(row, (list, tuple)) and len(row) > 0:
                            inserted_id = row[0]
                except Exception as exc:
                    logger.debug("Could not fetch inserted_id: %s", exc)

                # Récupérer les soldes clients après
                client_balances_after = {}
                if "clients" in table_names:
                    rows = conn.execute("SELECT id, name, current_balance FROM clients_with_stats").fetchall()
                    client_balances_after = {r[0]: r[2] for r in rows}

                res_info = {
                    "inserted_id": inserted_id,
                    "rowcount": rowcount,
                    "balances_before": client_balances_before,
                    "balances_after": client_balances_after,
                }
                raise DryRunRollback(res_info)
        except DryRunRollback as dr:
            res_info = dr.data
            inserted_id = res_info["inserted_id"]
            rowcount = res_info["rowcount"]
            client_balances_before = res_info["balances_before"]
            client_balances_after = res_info["balances_after"]

            parts = ["📝 **[Simulation] Résumé des modifications de données :**"]
            if inserted_id:
                parts.append(
                    f"• Création d'un nouvel enregistrement (ID temporaire : `{inserted_id}`) dans la table `{', '.join(table_names)}`."
                )
            elif rowcount is not None and rowcount > 0:
                parts.append(f"• Modification de `{rowcount}` ligne(s) dans la table `{', '.join(table_names)}`.")
            else:
                parts.append(f"• Exécution d'une modification sur la table `{', '.join(table_names)}`.")

            for cid, (name, bal_before) in client_balances_before.items():
                bal_before_val = float(bal_before or 0.0)
                bal_after_val = float(client_balances_after.get(cid) or 0.0)
                if bal_before_val != bal_after_val:
                    parts.append(
                        f"   - Le solde de **{name}** passe de `{bal_before_val:,.2f} DA` à `{bal_after_val:,.2f} DA`."
                    )

            return "\n".join(parts)
    except Exception as e:
        return f"⚠️ La simulation (dry-run) a échoué : {str(e)}"


def execute_write_sql(query: str) -> Dict[str, Any]:
    """Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour modifier, ajouter ou supprimer des données."""
    validation = guard_write_sql(query)
    if not validation.ok:
        return {"error": validation.error}

    query_to_run = validation.sql_to_run or query

    # Vérification de sécurité sur tous les statements et auto-évaluation
    auto_eval_reports = []
    for stmt in validation.statements:
        if stmt is None:
            continue

        # Auto-évaluation pour UPDATE et DELETE
        if stmt.__class__.__name__.lower() in ("update", "delete"):
            try:
                tbl_expr = stmt.find(sqlglot.exp.Table)
                if tbl_expr:
                    select_stmt = sqlglot.exp.select("*").from_(tbl_expr)
                    where_node = stmt.args.get("where")
                    if where_node:
                        select_stmt = select_stmt.where(where_node.this)
                    select_stmt = select_stmt.limit(100)
                    select_query = select_stmt.sql(dialect="postgres")

                    eval_rows = db_manager.query_db(select_query)

                    preview_sample = []
                    for r in eval_rows[:5]:
                        try:
                            preview_sample.append(dict(r))
                        except Exception:
                            preview_sample.append(list(r))

                    where_clause_str = (
                        where_node.sql(dialect="postgres").strip()
                        if where_node
                        else "Aucune restriction (toutes les lignes !)"
                    )
                    auto_eval_reports.append(
                        {
                            "table_name": tbl_expr.sql(dialect="postgres"),
                            "where_clause": where_clause_str,
                            "rows_affected_preview": len(eval_rows),
                            "preview_sample": serialize_for_json(preview_sample),
                        }
                    )
                    if len(eval_rows) > 0 and not where_node:
                        logger.warning(
                            "ATTENTION : Modification SQL d'écriture sans clause WHERE sur la table %s (%s lignes ciblées)",
                            tbl_expr.sql(dialect="postgres"),
                            len(eval_rows),
                        )
            except Exception as eval_err:
                logger.error("Auto-évaluation SQL échouée : %s", eval_err)

    clean_query = query.strip().lower()
    has_returning = "returning" in clean_query

    try:
        with db_manager.db_transaction() as conn:
            # Limiter le temps d'exécution des requêtes IA à 10s
            conn.execute("SET LOCAL statement_timeout = '10000'")
            cur = conn.execute(query_to_run)
            inserted_id = None
            if has_returning:
                try:
                    row = cur.fetchone()
                    if row:
                        if isinstance(row, dict):
                            inserted_id = row.get("id")
                        elif isinstance(row, (list, tuple)) and len(row) > 0:
                            inserted_id = row[0]
                except Exception as exc:
                    logger.debug("Could not fetch inserted_id: %s", exc)
            rowcount = getattr(cur, "rowcount", None)
            try:
                cur.close()
            except Exception as exc:
                logger.debug("Error closing cursor: %s", exc)
            result: Dict[str, Any] = {"success": True}
            if auto_eval_reports:
                result["auto_evaluation"] = auto_eval_reports
            if inserted_id is not None:
                result["inserted_id"] = inserted_id
                result["message"] = f"Opération réussie. ID créé : {inserted_id}."
            elif rowcount is not None:
                result["rowcount"] = rowcount
                result["message"] = f"{rowcount} ligne(s) affectée(s)."
            else:
                result["message"] = "Opération exécutée avec succès."
            return result
    except Exception as e:
        logger.error("execute_write_sql error for query %s: %s", query_to_run, e, exc_info=True)
        return {"error": f"Erreur SQL lors de l'écriture : {str(e)}"}
