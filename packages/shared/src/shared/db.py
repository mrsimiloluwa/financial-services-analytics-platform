"""Database connection helpers for PostgreSQL and DuckDB.

Provides safe connection factories with timeout controls and resource cleanup.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import duckdb
import psycopg
from psycopg import sql

from shared.config import Settings, get_settings

TEST_DATABASE_NAME = "analytics_platform_test"


@contextmanager
def get_postgres_connection(
    settings: Settings | None = None,
) -> Generator[Any, None, None]:
    """Context manager yielding an active database connection.

    When running in embedded mode (DATABASE_BACKEND=duckdb or unset POSTGRES_HOST),
    yields an in-memory DuckDB connection. Otherwise connects to PostgreSQL.
    """
    cfg = settings or get_settings()
    if cfg.is_duckdb:
        from shared.duckdb_reader import get_duckdb_reader_connection

        with get_duckdb_reader_connection(use_test_db=False) as duck_conn:
            yield duck_conn
        return

    conn = psycopg.connect(
        conninfo=cfg.postgres_connection_string,
        connect_timeout=cfg.db_timeout_seconds,
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_postgres_reader_connection(
    settings: Settings | None = None,
    use_test_db: bool = False,
) -> Generator[Any, None, None]:
    """Context manager yielding a read-only database connection.

    When running in embedded mode (DATABASE_BACKEND=duckdb or unset POSTGRES_HOST),
    yields an in-memory DuckDB reader loaded with packaged analytical marts from
    sample_data/. Otherwise connects to PostgreSQL under analytics_reader role.
    """
    cfg = settings or get_settings()
    if cfg.is_duckdb:
        from shared.duckdb_reader import get_duckdb_reader_connection

        with get_duckdb_reader_connection(use_test_db=use_test_db) as duck_conn:
            yield duck_conn
        return

    conninfo = (
        cfg.postgres_reader_test_connection_string
        if use_test_db
        else cfg.postgres_reader_connection_string
    )
    conn = psycopg.connect(
        conninfo=conninfo,
        connect_timeout=5,  # 5-second connection timeout for reader
        autocommit=True,  # Read-only queries don't need transaction wrapping
    )
    try:
        yield conn
    finally:
        conn.close()


def ensure_test_database_exists(settings: Settings | None = None) -> str:
    """Idempotently create analytics_platform_test if it does not exist.

    Never drops or modifies any existing database.
    """
    cfg = settings or get_settings()
    if cfg.postgres_test_db != TEST_DATABASE_NAME:
        raise ValueError(
            f"Refusing to provision non-standard test database '{cfg.postgres_test_db}'. "
            f"Expected '{TEST_DATABASE_NAME}'."
        )

    # First check if we can connect directly (e.g., in CI where analytics_platform_test is default)
    try:
        with (
            psycopg.connect(
                conninfo=cfg.postgres_test_connection_string,
                connect_timeout=cfg.db_timeout_seconds,
                autocommit=True,
            ) as test_conn,
            test_conn.cursor() as cur,
        ):
            cur.execute("SELECT current_database();")
            row = cur.fetchone()
            if row and row[0] == TEST_DATABASE_NAME:
                return TEST_DATABASE_NAME
    except psycopg.OperationalError:
        pass

    # Connect to the development/maintenance database to issue CREATE DATABASE
    with (
        psycopg.connect(
            conninfo=cfg.postgres_connection_string,
            connect_timeout=cfg.db_timeout_seconds,
            autocommit=True,
        ) as admin_conn,
        admin_conn.cursor() as cur,
    ):
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s;",
            (TEST_DATABASE_NAME,),
        )
        if cur.fetchone() is None:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DATABASE_NAME)))

    return TEST_DATABASE_NAME


@contextmanager
def get_test_postgres_connection(
    settings: Settings | None = None,
) -> Generator[psycopg.Connection[Any], None, None]:
    """Context manager yielding a PostgreSQL connection strictly to analytics_platform_test."""
    cfg = settings or get_settings()
    ensure_test_database_exists(cfg)
    conn = psycopg.connect(
        conninfo=cfg.postgres_test_connection_string,
        connect_timeout=cfg.db_timeout_seconds,
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database();")
            row = cur.fetchone()
            active_db = str(row[0]) if row else ""
        if active_db != TEST_DATABASE_NAME:
            raise RuntimeError(
                f"Test connection safety check failed: expected '{TEST_DATABASE_NAME}', "
                f"got '{active_db}'."
            )
        yield conn
    finally:
        conn.close()


def get_duckdb_connection(
    database: str = ":memory:",
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Return an active DuckDB connection."""
    return duckdb.connect(database=database, read_only=read_only)
