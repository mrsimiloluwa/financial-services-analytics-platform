"""PostgreSQL DDL definitions for raw and staging banking schemas."""

from pathlib import Path

import psycopg

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


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


def truncate_raw_tables(conn: psycopg.Connection) -> None:
    """Clean all raw tables before a fresh full simulation load."""
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
