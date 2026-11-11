"""PostgreSQL DDL definitions for raw and staging banking schemas."""

from pathlib import Path

import psycopg
from shared.db import TEST_DATABASE_NAME

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def assert_is_test_database(conn: psycopg.Connection) -> str:
    """Verify the active PostgreSQL connection is strictly analytics_platform_test.

    Raises PermissionError if connected to analytics_platform or any other database.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT current_database();")
        row = cur.fetchone()
        active_db = str(row[0]) if row else ""

    if active_db != TEST_DATABASE_NAME:
        raise PermissionError(
            f"Safety guard blocked destructive operation on database '{active_db}'. "
            f"Destructive integration test operations are only permitted on '{TEST_DATABASE_NAME}'."
        )
    return active_db


def load_sql_file(filename: str) -> str:
    """Load SQL statement string from data_platform/sql directory."""
    path = SQL_DIR / filename
    return path.read_text(encoding="utf-8")


def init_database_schemas(conn: psycopg.Connection) -> None:
    """Initialize raw and staging schemas in PostgreSQL using governed SQL scripts."""
    raw_ddl = load_sql_file("schema_raw.sql")
    staging_ddl = load_sql_file("schema_staging.sql")

    with conn.cursor() as cur:
        cur.execute(raw_ddl)
        cur.execute(staging_ddl)
    conn.commit()


def truncate_staging_tables(conn: psycopg.Connection) -> None:
    """Clean all staging tables before a batch COPY operation."""
    staging_tables = [
        "staging.gl_accounts",
        "staging.customers",
        "staging.accounts",
        "staging.overdraft_facilities",
        "staging.fx_rates",
        "staging.transactions",
        "staging.journals",
        "staging.ledger_entries",
        "staging.fee_assessments",
        "staging.fee_collections",
        "staging.revenue_recognitions",
    ]
    with conn.cursor() as cur:
        for tbl in staging_tables:
            cur.execute(f"TRUNCATE TABLE {tbl};")
    conn.commit()


def truncate_raw_tables(
    conn: psycopg.Connection,
    *,
    allow_non_test_db: bool = False,
) -> None:
    """Clean all raw tables before a fresh full simulation load.

    Refuses to execute unless connected to analytics_platform_test, or when
    allow_non_test_db=True is explicitly passed by the CLI --reset flag.
    """
    if not allow_non_test_db:
        assert_is_test_database(conn)

    raw_tables = [
        "raw.ingestion_batch_manifests",
        "raw.revenue_recognitions",
        "raw.fee_collections",
        "raw.fee_assessments",
        "raw.ledger_entries",
        "raw.journals",
        "raw.transactions",
        "raw.fx_rates",
        "raw.overdraft_facilities",
        "raw.accounts",
        "raw.customers",
        "raw.gl_accounts",
    ]
    with conn.cursor() as cur:
        for tbl in raw_tables:
            cur.execute(f"TRUNCATE TABLE {tbl} CASCADE;")
    conn.commit()
