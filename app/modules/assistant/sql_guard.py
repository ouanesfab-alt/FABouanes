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
    "into",
    "lock",
}

WRITE_FORBIDDEN_NODE_PARTS = {
    "create",
    "drop",
    "alter",
    "truncate",
    "command",
    "grant",
    "revoke",
    "into",
}

WRITE_STATEMENT_NAMES = {"insert", "update", "delete"}
PROTECTED_TABLE_NAMES = {
    "app_settings",
    "pg_authid",
    "pg_roles",
    "pg_shadow",
    "pg_user",
    "users",
    "client_keys",
    "api_refresh_tokens",
    "audit_logs",
}
PROTECTED_SCHEMA_NAMES = {"information_schema", "pg_catalog"}

FORBIDDEN_FUNCTION_NAMES = {
    "table_to_xml",
    "query_to_xml",
    "cursor_to_xml",
    "table_to_xml_and_xmlschema",
    "query_to_xml_and_xmlschema",
    "schema_to_xml",
    "schema_to_xml_and_xmlschema",
    "database_to_xml",
    "database_to_xml_and_xmlschema",
    "pg_sleep",
    "pg_sleep_for",
    "pg_sleep_until",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_stat_file",
    "pg_ls_dir",
    "lo_import",
    "lo_export",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "setval",
    "nextval",
    "set_config",
    "current_setting",
}

ALLOWED_WRITE_TABLES_BASE = {
    "contacts",
    "catalog_items",
    "catalog",
    "production",
    "logs",
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


def get_allowed_write_tables() -> set[str]:
    """Generates allowed write tables dynamically from schema metadata and base set."""
    tables = set(ALLOWED_WRITE_TABLES_BASE)
    try:
        from sqlmodel import SQLModel

        for tbl_name in SQLModel.metadata.tables.keys():
            if tbl_name not in PROTECTED_TABLE_NAMES:
                tables.add(tbl_name.lower())
    except Exception:
        pass
    return tables


ALLOWED_WRITE_TABLES = ALLOWED_WRITE_TABLES_BASE


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


def _contains_forbidden_function(statement: Any) -> str | None:
    for node in statement.find_all(sqlglot.exp.Expression):
        func_name = None
        if isinstance(node, sqlglot.exp.Anonymous):
            func_name = str(node.this).lower()
        elif isinstance(node, sqlglot.exp.Func):
            func_name = node.sql_name().lower() if hasattr(node, "sql_name") else node.__class__.__name__.lower()
        if func_name and func_name in FORBIDDEN_FUNCTION_NAMES:
            return func_name
    return None


def _contains_protected_table(statement: Any) -> bool:
    for table_node in statement.find_all(sqlglot.exp.Table):
        table_name = table_node.name.lower()
        db_name = str(table_node.args.get("db") or "").strip('"').lower()
        catalog_name = str(table_node.args.get("catalog") or "").strip('"').lower()
        table_parts = {part for part in (catalog_name, db_name, table_name) if part}
        if table_name in PROTECTED_TABLE_NAMES or table_parts & PROTECTED_SCHEMA_NAMES:
            return True

    # Block literals referencing protected tables or schemas (e.g. table_to_xml('users', ...))
    for lit in statement.find_all(sqlglot.exp.Literal):
        if lit.is_string:
            val = str(lit.this).strip().lower()
            if val in PROTECTED_TABLE_NAMES or val in PROTECTED_SCHEMA_NAMES:
                return True
    return False


def _has_limit(statement: Any) -> bool:
    return any(isinstance(node, sqlglot.exp.Limit) for node in statement.find_all(sqlglot.exp.Expression))


def _get_write_target_tables(statement: Any) -> set[str]:
    """Extract all target table(s) of any INSERT/UPDATE/DELETE statement or CTEs."""
    tables: set[str] = set()
    for insert_node in statement.find_all(sqlglot.exp.Insert):
        tbl = insert_node.find(sqlglot.exp.Table)
        if tbl and tbl.name:
            tables.add(tbl.name.lower())
    for update_node in statement.find_all(sqlglot.exp.Update):
        tbl = update_node.find(sqlglot.exp.Table)
        if tbl and tbl.name:
            tables.add(tbl.name.lower())
    for delete_node in statement.find_all(sqlglot.exp.Delete):
        for tbl in delete_node.find_all(sqlglot.exp.Table):
            if tbl.name:
                tables.add(tbl.name.lower())
            break
    return tables


def _has_valid_where_clause(statement: Any) -> tuple[bool, str | None]:
    if not isinstance(statement, (sqlglot.exp.Update, sqlglot.exp.Delete)):
        return True, None

    where_node = statement.args.get("where")
    if where_node is None:
        return (
            False,
            "La clause WHERE est obligatoire pour les opérations de mise à jour (UPDATE) et de suppression (DELETE).",
        )

    expr = where_node.this
    if expr is None:
        return False, "La clause WHERE ne peut pas être vide."

    # Check for direct TRUE or literal true boolean
    if isinstance(expr, sqlglot.exp.Boolean) and expr.this is True:
        return False, "La clause WHERE ne peut pas être triviale (ex: WHERE TRUE)."

    if isinstance(expr, (sqlglot.exp.Literal, sqlglot.exp.Null)):
        return False, "La clause WHERE ne peut pas être triviale."

    # Check for tautology comparisons (e.g. 1 = 1, 'a' = 'a')
    if isinstance(expr, sqlglot.exp.EQ):
        left = expr.left
        right = expr.right
        if isinstance(left, sqlglot.exp.Literal) and isinstance(right, sqlglot.exp.Literal):
            if str(left.this) == str(right.this):
                return False, "La clause WHERE ne peut pas être une tautologie (ex: WHERE 1 = 1)."
        if isinstance(left, sqlglot.exp.Column) and isinstance(right, sqlglot.exp.Column):
            if left.name.lower() == right.name.lower():
                return False, "La clause WHERE ne peut pas comparer une colonne à elle-même (ex: WHERE id = id)."

    # Must contain at least one column reference
    columns = list(where_node.find_all(sqlglot.exp.Column))
    if not columns:
        return False, "La clause WHERE doit référencer au moins une colonne."

    return True, None


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

    forbidden_func = _contains_forbidden_function(statement)
    if forbidden_func:
        return SqlValidationResult(
            False,
            f"Appel à la fonction interdite '{forbidden_func}'.",
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

    forbidden_func = _contains_forbidden_function(statement)
    if forbidden_func:
        return SqlValidationResult(
            False,
            f"Appel à la fonction interdite '{forbidden_func}'.",
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
    allowed_tables = get_allowed_write_tables()
    non_allowed = target_tables - allowed_tables

    if non_allowed:
        bad = ", ".join(sorted(non_allowed))
        return SqlValidationResult(
            False,
            f"Table(s) non autorisée(s) en écriture : {bad}. Seules les tables métier de l'application sont modifiables.",
            statements=parsed.statements,
            statement=statement,
        )

    # Mandatory WHERE clause check for all UPDATE / DELETE statements in the tree (including CTEs)
    for op in statement.find_all((sqlglot.exp.Update, sqlglot.exp.Delete)):
        ok, err_msg = _has_valid_where_clause(op)
        if not ok:
            return SqlValidationResult(
                False,
                err_msg,
                statements=parsed.statements,
                statement=statement,
            )

    return SqlValidationResult(True, statements=parsed.statements, statement=statement, sql_to_run=query)
