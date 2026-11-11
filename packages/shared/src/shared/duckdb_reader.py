"""Standalone DuckDB reader adapter for packaged synthetic marts.

Provides zero-credential, read-only analytical query execution over
governed CSV exports packaged in sample_data/ for Streamlit Community Cloud
and local offline demonstration.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

_DEV_DUCKDB_CON: duckdb.DuckDBPyConnection | None = None
_TEST_DUCKDB_CON: duckdb.DuckDBPyConnection | None = None


def _find_repo_root() -> Path:
    """Locate repository root directory containing sample_data/."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "sample_data").exists():
            return current
        current = current.parent
    # Fallback to current working directory
    return Path.cwd()


def _init_duckdb_instance(data_dir: Path) -> duckdb.DuckDBPyConnection:
    """Initialize an in-memory DuckDB instance and load packaged marts under analytics schema."""
    logger.info("Initializing DuckDB in-memory analytical warehouse from %s", data_dir)
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA IF NOT EXISTS analytics;")
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")

    # Register PostgreSQL compatibility macros
    con.execute("CREATE OR REPLACE MACRO to_char(d, fmt) AS substring(cast(d as varchar), 1, 7);")

    table_files = {
        "dim_customers": data_dir / "dim_customers.csv",
        "dim_accounts": data_dir / "dim_accounts.csv",
        "fct_customer_revenue": data_dir / "customer_revenue.csv",
        "fct_fee_assessments": data_dir / "fee_assessments_analytics.csv",
        "fct_fee_collections": data_dir / "fct_fee_collections.csv",
        "fct_transactions": data_dir / "transaction_analytics.csv",
    }

    for table_name, csv_path in table_files.items():
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Required sample data file missing for '{table_name}': {csv_path}"
            )
        # Load as in-memory table for sub-millisecond query execution
        con.execute(
            f"CREATE TABLE analytics.{table_name} AS "
            f"SELECT * FROM read_csv_auto('{csv_path.as_posix()}');"
        )
        logger.debug("Loaded analytics.%s into DuckDB", table_name)

    # Optionally load raw tables if present for lineage/reconciliation checks
    raw_files = {
        "fee_assessments": data_dir / "fee_assessments.csv",
        "transactions": data_dir / "transactions.csv",
        "customers": data_dir / "customers.csv",
        "accounts": data_dir / "accounts.csv",
        "fee_collections": data_dir / "fee_collections.csv",
    }
    for table_name, csv_path in raw_files.items():
        if csv_path.exists():
            con.execute(
                f"CREATE TABLE raw.{table_name} AS "
                f"SELECT * FROM read_csv_auto('{csv_path.as_posix()}');"
            )

    return con


def get_duckdb_marts_connection(use_test_db: bool = False) -> duckdb.DuckDBPyConnection:
    """Retrieve or initialize cached DuckDB connection for target environment."""
    global _DEV_DUCKDB_CON, _TEST_DUCKDB_CON
    repo_root = _find_repo_root()

    if use_test_db:
        if _TEST_DUCKDB_CON is None:
            _TEST_DUCKDB_CON = _init_duckdb_instance(repo_root / "sample_data" / "test")
        return _TEST_DUCKDB_CON

    if _DEV_DUCKDB_CON is None:
        _DEV_DUCKDB_CON = _init_duckdb_instance(repo_root / "sample_data")
    return _DEV_DUCKDB_CON


class DuckDBColDescription:
    """Mimic DB-API / psycopg column description object."""

    def __init__(self, name: str) -> None:
        self.name = name


class DuckDBCursorAdapter:
    """DB-API compatible cursor adapter wrapping DuckDBPyConnection cursor."""

    def __init__(self, duck_cursor: Any, dict_rows: bool = False) -> None:
        self._cur = duck_cursor
        self._dict_rows = dict_rows

    def __enter__(self) -> DuckDBCursorAdapter:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def execute(self, query: str, params: Any = None) -> DuckDBCursorAdapter:
        """Execute query, ignoring PostgreSQL-specific session SETs and translating %s to ?."""
        cleaned = query.strip()
        # Silently ignore PostgreSQL-specific session configuration
        if cleaned.upper().startswith("SET STATEMENT_TIMEOUT") or cleaned.upper().startswith(
            "SET SEARCH_PATH"
        ):
            return self

        if params is not None:
            duck_query = re.sub(r"%s", "?", cleaned)
            self._cur.execute(duck_query, list(params) if isinstance(params, tuple) else params)
        else:
            self._cur.execute(cleaned)
        return self

    def fetchone(self) -> Any:
        row = self._cur.fetchone()
        if row is None or not self._dict_rows:
            return row
        cols = [desc[0] for desc in self._cur.description]
        return dict(zip(cols, row, strict=False))

    def fetchall(self) -> list[Any]:
        rows = self._cur.fetchall()
        if not self._dict_rows:
            return rows
        cols = [desc[0] for desc in self._cur.description]
        return [dict(zip(cols, r, strict=False)) for r in rows]

    def fetchmany(self, size: int = 1) -> list[Any]:
        rows = self._cur.fetchmany(size)
        if not self._dict_rows:
            return rows
        cols = [desc[0] for desc in self._cur.description]
        return [dict(zip(cols, r, strict=False)) for r in rows]

    @property
    def description(self) -> list[DuckDBColDescription]:
        if not self._cur.description:
            return []
        return [DuckDBColDescription(d[0]) for d in self._cur.description]

    def close(self) -> None:
        self._cur.close()


class DuckDBConnectionContext:
    """Context manager wrapping DuckDB connection providing cursor() method."""

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def __enter__(self) -> DuckDBConnectionContext:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def cursor(self, row_factory: Any = None) -> DuckDBCursorAdapter:
        dict_mode = row_factory is not None
        return DuckDBCursorAdapter(self._con.cursor(), dict_rows=dict_mode)

    def close(self) -> None:
        pass


@contextmanager
def get_duckdb_reader_connection(
    use_test_db: bool = False,
) -> Generator[DuckDBConnectionContext, None, None]:
    """Context manager yielding a read-only DuckDB analytical connection."""
    con = get_duckdb_marts_connection(use_test_db=use_test_db)
    ctx = DuckDBConnectionContext(con)
    try:
        yield ctx
    finally:
        pass
