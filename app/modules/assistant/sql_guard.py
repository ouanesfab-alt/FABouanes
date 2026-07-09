from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot


READONLY_FORBIDDEN_NODE_PARTS = {
    "insert",
    "update",
    "delete",
    "create",
    "drop",
    "alter",
    "truncate",
    "command",
    "grant",
    "revoke",
}

WRITE_FORBIDDEN_NODE_PARTS = {
    "create",
    "drop",
    "alter",
    "truncate",
    "command",
    "grant",
    "revoke",
}

WRITE_STATEMENT_NAMES = {"insert", "update", "delete"}
PROTECTED_TABLE_NAMES = {
    "app_settings",
    "pg_authid",
    "pg_roles",
    "pg_shadow",
    "pg_user",
    "users",
}
PROTECTED_SCHEMA_NAMES = {"information_schema", "pg_catalog"}

# Tables that Sabrina is explicitly allowed to write to.
# Any INSERT/UPDATE/DELETE targeting a table NOT in this set will be blocked.
ALLOWED_WRITE_TABLES = {
    "clients",
    "suppliers",
    "finished_products",
    "raw_materials",
    "sales",
    "raw_sales",
    "purchases",
    "payments",
    "expenses",
    "production_batches",
    "production_batch_items",
    "saved_recipes",
    "saved_recipe_items",
    "supplier_payments",
    "sale_documents",
    "purchase_documents",
    "stock_movements",
    "stock_alerts",
    "sabrina_memory",
}


@dataclass
class SqlValidationResult:
    ok: bool
    error: str | None = None
    statements: list[Any] = field(default_factory=list)
    statement: Any | None = None
    sql_to_run: str | None = None


def _parse_postgres_sql(query: str) -> SqlValidationResult:
    try:
        statements = sqlglot.parse(query, read="postgres")
    except Exception as exc:
        return SqlValidationResult(False, f"Erreur de syntaxe ou de validation SQL : {exc}")

    if not statements:
        return SqlValidationResult(False, "Aucune requête SQL valide fournie.")

    return SqlValidationResult(True, statements=statements)


def _contains_forbidden_node(statement: Any, forbidden_parts: set[str]) -> str | None:
    for node in statement.find_all(sqlglot.exp.Expression):
        name = node.__class__.__name__.lower()
        if any(part in name for part in forbidden_parts):
            return name
    return None


def _contains_protected_table(statement: Any) -> bool:
    for table_node in statement.find_all(sqlglot.exp.Table):
        table_name = table_node.name.lower()
        db_name = str(table_node.args.get("db") or "").strip('"').lower()
        catalog_name = str(table_node.args.get("catalog") or "").strip('"').lower()
        table_parts = {part for part in (catalog_name, db_name, table_name) if part}
        if table_name in PROTECTED_TABLE_NAMES or table_parts & PROTECTED_SCHEMA_NAMES:
            return True
    return False


def _has_limit(statement: Any) -> bool:
    return any(isinstance(node, sqlglot.exp.Limit) for node in statement.find_all(sqlglot.exp.Expression))


def _get_write_target_tables(statement: Any) -> set[str]:
    """Extract the primary target table(s) of an INSERT/UPDATE/DELETE statement."""
    tables: set[str] = set()
    # INSERT INTO <table>
    if isinstance(statement, sqlglot.exp.Insert):
        # sqlglot wraps the target in a Table node inside statement.this
        tbl = statement.find(sqlglot.exp.Table)
        if tbl and tbl.name:
            tables.add(tbl.name.lower())
    # UPDATE <table>
    elif isinstance(statement, sqlglot.exp.Update):
        tbl = statement.find(sqlglot.exp.Table)
        if tbl and tbl.name:
            tables.add(tbl.name.lower())
    # DELETE FROM <table>
    elif isinstance(statement, sqlglot.exp.Delete):
        for tbl in statement.find_all(sqlglot.exp.Table):
            if tbl.name:
                tables.add(tbl.name.lower())
            break  # only the first (target) table
    return tables


def validate_readonly_sql(query: str, default_limit: int = 100) -> SqlValidationResult:
    parsed = _parse_postgres_sql(query)
    if not parsed.ok:
        return parsed

    if len(parsed.statements) > 1:
        return SqlValidationResult(False, "Une seule requête SQL SELECT est autorisée à la fois.")

    statement = parsed.statements[0]
    if not isinstance(statement, (sqlglot.exp.Select, sqlglot.exp.Union, sqlglot.exp.Query)):
        return SqlValidationResult(
            False,
            "Opération non autorisée (interdite) : seules les requêtes SELECT de lecture sont autorisées.",
            statements=parsed.statements,
            statement=statement,
        )

    forbidden_node = _contains_forbidden_node(statement, READONLY_FORBIDDEN_NODE_PARTS)
    if forbidden_node:
        return SqlValidationResult(
            False,
            f"Opération de type '{forbidden_node}' interdite en lecture seule.",
            statements=parsed.statements,
            statement=statement,
        )

    if _contains_protected_table(statement):
        return SqlValidationResult(
            False,
            "Acces a une table protegee interdit.",
            statements=parsed.statements,
            statement=statement,
        )

    sql_to_run = query
    if not _has_limit(statement):
        try:
            sql_to_run = statement.copy().limit(default_limit).sql(dialect="postgres")
        except Exception:
            sql_to_run = f"{query.rstrip(';')} LIMIT {default_limit}"

    return SqlValidationResult(True, statements=parsed.statements, statement=statement, sql_to_run=sql_to_run)


def validate_write_sql(query: str) -> SqlValidationResult:
    parsed = _parse_postgres_sql(query)
    if not parsed.ok:
        return parsed

    if len(parsed.statements) > 1:
        return SqlValidationResult(False, "Une seule requête SQL d'écriture est autorisée à la fois.")

    statement = parsed.statements[0]
    statement_name = statement.__class__.__name__.lower()
    if statement_name not in WRITE_STATEMENT_NAMES:
        return SqlValidationResult(
            False,
            "Opération non autorisée : seules les requêtes INSERT, UPDATE et DELETE sont autorisées en écriture.",
            statements=parsed.statements,
            statement=statement,
        )

    forbidden_node = _contains_forbidden_node(statement, WRITE_FORBIDDEN_NODE_PARTS)
    if forbidden_node:
        return SqlValidationResult(
            False,
            f"Opération de structure/droit '{forbidden_node}' interdite pour des raisons de sécurité.",
            statements=parsed.statements,
            statement=statement,
        )

    if _contains_protected_table(statement):
        return SqlValidationResult(
            False,
            "Acces a une table protegee interdit.",
            statements=parsed.statements,
            statement=statement,
        )

    # Allow-list check: only write to explicitly permitted tables
    target_tables = _get_write_target_tables(statement)
    non_allowed = target_tables - ALLOWED_WRITE_TABLES
    if non_allowed:
        bad = ", ".join(sorted(non_allowed))
        return SqlValidationResult(
            False,
            f"Table(s) non autorisée(s) en écriture : {bad}. Seules les tables métier de l'application sont modifiables.",
            statements=parsed.statements,
            statement=statement,
        )

    return SqlValidationResult(True, statements=parsed.statements, statement=statement, sql_to_run=query)
