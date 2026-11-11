"""Read-only SQL execution engine utilizing least-privilege analytics_reader role."""

from __future__ import annotations

import logging
import time
from typing import Any

import psycopg
from ai_services.schemas import QueryResult
from psycopg.rows import dict_row
from shared.config import Settings, get_settings
from shared.db import get_postgres_reader_connection

logger = logging.getLogger(__name__)


class SQLExecutionEngine:
    """Executes validated read-only SQL queries against PostgreSQL under analytics_reader role."""

    def __init__(self, settings: Settings | None = None, use_test_db: bool = False) -> None:
        """Initialize engine with application settings and target database flag."""
        self.settings = settings or get_settings()
        self.use_test_db = use_test_db

    def execute_query(self, sql_query: str, max_rows: int = 1000) -> QueryResult:
        """Execute a validated query with a strict 5-second timeout and row limit."""
        start_time = time.perf_counter()

        try:
            with (
                get_postgres_reader_connection(
                    settings=self.settings, use_test_db=self.use_test_db
                ) as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                # Enforce 5-second statement timeout at session level
                cur.execute("SET statement_timeout = '5000ms';")

                cur.execute(sql_query)

                # Fetch rows up to max_rows + 1 to detect truncation
                raw_rows = cur.fetchmany(max_rows + 1)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

                truncated = len(raw_rows) > max_rows
                result_rows = raw_rows[:max_rows]

                columns = [desc.name for desc in cur.description] if cur.description else []

                # Convert non-serializable objects (Decimals, dates, UUIDs) to strings/floats
                formatted_rows: list[dict[str, Any]] = []
                for row in result_rows:
                    formatted_row: dict[str, Any] = {}
                    for k, v in row.items():
                        if hasattr(v, "isoformat"):
                            formatted_row[k] = v.isoformat()
                        elif hasattr(v, "__float__"):
                            formatted_row[k] = float(v)
                        else:
                            formatted_row[k] = v
                    formatted_rows.append(formatted_row)

                logger.info(
                    "Executed query in %.2fms | Rows: %d | Truncated: %s",
                    duration_ms,
                    len(formatted_rows),
                    truncated,
                )

                return QueryResult(
                    columns=columns,
                    rows=formatted_rows,
                    row_count=len(formatted_rows),
                    execution_time_ms=duration_ms,
                    truncated=truncated,
                )

        except psycopg.errors.QueryCanceled as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning("Query exceeded 5-second statement timeout: %s", exc)
            return QueryResult(
                execution_time_ms=duration_ms,
                error="Query execution cancelled: exceeded 5000ms statement timeout limit.",
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error("Database query execution failed: %s", exc)
            return QueryResult(
                execution_time_ms=duration_ms,
                error=f"Database execution error: {exc}",
            )
