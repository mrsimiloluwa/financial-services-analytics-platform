"""SQL security validator enforcing AST safety boundaries using SQLGlot."""

from __future__ import annotations

import logging

import sqlglot
from ai_services.schemas import SQLValidationResult
from data_platform.security.provision_reader import APPROVED_QUERYABLE_MARTS
from sqlglot import exp

logger = logging.getLogger(__name__)

# Strict allowed schemas for analytical queries
PERMITTED_SCHEMAS = {"analytics", ""}
DISALLOWED_SCHEMAS = {
    "raw",
    "staging",
    "intermediate",
    "metadata",
    "public",
    "information_schema",
    "pg_catalog",
    "pg_toast",
}

# Forbidden AST statement types (DDL, DML, administrative commands, data creation)
FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Pragma,
    exp.Into,
    exp.Merge,
    exp.Grant,
    exp.Revoke,
)

# Dangerous PostgreSQL functions that could facilitate exfiltration or DoS
DANGEROUS_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "query_to_xml",
    "database_to_xml",
    "schema_to_xml",
    "table_to_xml",
    "dblink",
    "dblink_exec",
    "lo_import",
    "lo_export",
    "lo_unlink",
    "system",
    "sh",
    "cmd",
}

RESTRICTED_COLUMN_PATTERNS = {"password", "secret", "api_key", "token", "private_key", "credential"}


class SQLGlotASTValidator:
    """Enforces strict read-only, table allowlist, CTE safety, and AST security controls."""

    def __init__(
        self,
        dialect: str = "postgres",
        allowed_tables: set[str] | list[str] | None = None,
        max_limit: int = 1000,
    ) -> None:
        """Initialize validator with dialect and allowlist."""
        self.dialect = dialect
        self.allowed_tables = set(allowed_tables or APPROVED_QUERYABLE_MARTS)
        self.max_limit = max_limit

    def validate_and_sanitize(self, sql_query: str) -> SQLValidationResult:
        """Parse, validate, and inject safety limits into a SQL query string."""
        raw_sql = sql_query.strip().rstrip(";")

        # 1. Parse AST
        try:
            expressions = sqlglot.parse(raw_sql, read=self.dialect)
        except Exception as exc:
            return SQLValidationResult(
                is_valid=False,
                error_message=f"SQL syntax parse error: {exc}",
            )

        if not expressions or len(expressions) == 0:
            return SQLValidationResult(
                is_valid=False,
                error_message="Empty SQL query.",
            )

        # 2. Reject multi-statement queries (semicolon injection)
        if len(expressions) > 1:
            return SQLValidationResult(
                is_valid=False,
                error_message="Multiple statements detected. Semicolon-stacked queries are strictly prohibited.",
            )

        parsed = expressions[0]

        # 3. Reject DDL, DML, Command, and non-read expressions
        if isinstance(parsed, FORBIDDEN_EXPRESSIONS) or any(parsed.find_all(FORBIDDEN_EXPRESSIONS)):
            return SQLValidationResult(
                is_valid=False,
                error_message="Prohibited operation. Only read-only SELECT queries are permitted.",
            )

        if not isinstance(parsed, (exp.Select, exp.Union, exp.Query)):
            return SQLValidationResult(
                is_valid=False,
                error_message="Query root must be a read-only SELECT or UNION query expression.",
            )

        # 4. Prohibit Dangerous Functions
        for func_node in parsed.find_all((exp.Func, exp.Anonymous)):
            fname = func_node.name.lower() if hasattr(func_node, "name") and func_node.name else ""
            if fname in DANGEROUS_FUNCTIONS:
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Access denied to prohibited function '{fname}'.",
                )

        # 5. Extract CTE aliases defined in the query
        cte_aliases = {
            cte.alias.lower()
            for cte in parsed.find_all(exp.CTE)
            if hasattr(cte, "alias") and cte.alias
        }

        # 6. Table and Schema Boundary Enforcement
        tables_accessed: list[str] = []
        for table_node in parsed.find_all(exp.Table):
            table_name = table_node.name.lower()
            schema_name = table_node.db.lower() if table_node.db else ""

            # Check if reference is to an internally defined CTE alias
            if table_name in cte_aliases:
                if schema_name:
                    return SQLValidationResult(
                        is_valid=False,
                        error_message=(
                            f"Common table expression '{table_name}' cannot be schema-qualified with '{schema_name}'."
                        ),
                    )
                continue

            # Check for disallowed schemas (raw, staging, metadata, pg_catalog, public)
            if schema_name in DISALLOWED_SCHEMAS:
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Access denied to schema '{schema_name}'. Only 'analytics' marts are permitted.",
                )

            # Check if schema is explicitly anything other than analytics
            if schema_name and schema_name not in PERMITTED_SCHEMAS:
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Access denied to non-analytics schema '{schema_name}'.",
                )

            # Check table allowlist
            if table_name not in self.allowed_tables:
                return SQLValidationResult(
                    is_valid=False,
                    error_message=(
                        f"Table '{table_name}' is not in the governed queryable allowlist: "
                        f"{sorted(self.allowed_tables)}"
                    ),
                )

            tables_accessed.append(f"analytics.{table_name}")

            # Normalize schema to analytics if omitted
            if not table_node.db:
                table_node.set("db", exp.to_identifier("analytics"))

        if not tables_accessed and not cte_aliases:
            return SQLValidationResult(
                is_valid=False,
                error_message="Query does not reference any database tables.",
            )

        # 7. Column Classification Checks
        columns_accessed: list[str] = []
        for col_node in parsed.find_all(exp.Column):
            col_name = col_node.name.lower()
            if any(restr in col_name for restr in RESTRICTED_COLUMN_PATTERNS):
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Access denied to RESTRICTED security column '{col_name}'.",
                )
            columns_accessed.append(col_name)

        # 8. Row Limit Injection and Clamping: never raise a smaller user LIMIT, only cap larger
        # (or missing / non-literal) limits at max_limit.
        effective_limit = self.max_limit
        existing = parsed.args.get("limit")
        if existing is not None:
            expr = existing.args.get("expression")
            if isinstance(expr, exp.Literal) and expr.is_int:
                effective_limit = min(int(expr.this), self.max_limit)
        parsed = parsed.limit(effective_limit)
        sanitized_sql = parsed.sql(dialect=self.dialect)

        return SQLValidationResult(
            is_valid=True,
            sanitized_sql=sanitized_sql,
            tables_accessed=sorted(set(tables_accessed)),
            columns_accessed=sorted(set(columns_accessed)),
        )
