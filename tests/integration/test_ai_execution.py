"""Integration tests for read-only SQL execution engine and analytics_reader role."""

from __future__ import annotations

import psycopg
import pytest
from ai_services.execution.engine import SQLExecutionEngine
from data_platform.security.provision_reader import APPROVED_QUERYABLE_MARTS
from shared.config import get_settings
from shared.db import get_postgres_reader_connection


@pytest.fixture(autouse=True)
def require_live_postgres():
    if get_settings().is_duckdb:
        pytest.skip("PostgreSQL role permission tests require live PostgreSQL warehouse")


@pytest.fixture
def reader_engine() -> SQLExecutionEngine:
    return SQLExecutionEngine(use_test_db=True)


def test_reader_can_select_all_approved_marts(reader_engine: SQLExecutionEngine):
    """Verify analytics_reader has explicit SELECT privileges on all 6 approved queryable marts."""
    for mart in APPROVED_QUERYABLE_MARTS:
        result = reader_engine.execute_query(
            f"SELECT COUNT(*) AS total_count FROM analytics.{mart};"
        )
        assert result.error is None, f"Failed querying approved mart {mart}: {result.error}"
        assert result.row_count == 1
        assert result.execution_time_ms < 5000


def test_reader_denied_access_to_non_mart_analytics_views():
    """Verify analytics_reader is strictly denied from selecting non-mart views/tables within analytics schema."""
    for non_mart in [
        "stg_transactions",
        "stg_customers",
        "int_customer_revenue",
        "int_fee_lifecycle",
    ]:
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            get_postgres_reader_connection(use_test_db=True) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(f"SELECT * FROM analytics.{non_mart} LIMIT 1;")


def test_reader_denied_access_to_raw_schema():
    with (
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        get_postgres_reader_connection(use_test_db=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("SELECT * FROM raw.customers LIMIT 1;")


def test_reader_denied_access_to_metadata_schema():
    with (
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        get_postgres_reader_connection(use_test_db=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("SELECT * FROM metadata.model_metadata LIMIT 1;")


def test_reader_denied_write_dml():
    with (
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        get_postgres_reader_connection(use_test_db=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("DELETE FROM analytics.fct_customer_revenue WHERE 1=1;")


def test_statement_timeout_enforcement(reader_engine: SQLExecutionEngine):
    # Executing pg_sleep(6) should be aborted by 5000ms statement_timeout
    result = reader_engine.execute_query("SELECT pg_sleep(6);")
    assert result.error is not None
    assert "timeout" in result.error.lower()
