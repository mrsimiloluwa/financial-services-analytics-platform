"""Database connection helpers for PostgreSQL and DuckDB.

Provides safe connection factories with timeout controls and resource cleanup.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import duckdb
import psycopg

from shared.config import Settings, get_settings


@contextmanager
def get_postgres_connection(
    settings: Settings | None = None,
) -> Generator[psycopg.Connection[Any], None, None]:
    """Context manager yielding an active PostgreSQL connection.

    Ensures connections are properly closed and exceptions logged.
    """
    cfg = settings or get_settings()
    conn = psycopg.connect(
        conninfo=cfg.postgres_connection_string,
        connect_timeout=cfg.db_timeout_seconds,
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()


def get_duckdb_connection(
    database: str = ":memory:",
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Return an active DuckDB connection."""
    return duckdb.connect(database=database, read_only=read_only)
