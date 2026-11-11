"""Integration tests verifying the Phase 2 dbt analytics schema models and financial invariants."""

import os
from decimal import Decimal

import psycopg
import pytest
from data_platform.ingestion.ddl import assert_is_test_database
from shared.config import Settings
from shared.db import TEST_DATABASE_NAME, get_test_postgres_connection


@pytest.fixture
def pg_conn() -> psycopg.Connection:
    """Provide an isolated PostgreSQL connection (analytics_platform_test) for dbt testing."""
    settings = Settings()
    try:
        with get_test_postgres_connection(settings) as conn:
            active_db = assert_is_test_database(conn)
            assert active_db == TEST_DATABASE_NAME
            yield conn
    except psycopg.OperationalError as exc:
        if os.getenv("CI") == "true" or settings.app_env == "testing":
            pytest.fail(f"PostgreSQL connection failed in CI/testing environment: {exc}")
        pytest.skip(f"PostgreSQL container not accessible: {exc}")


def test_dbt_analytics_relations_exist(pg_conn: psycopg.Connection) -> None:
    """Verify all 26 dbt models (17 views and 9 tables) exist in the analytics schema."""
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = 'analytics';
        """)
        relations = {row[0]: row[1] for row in cur.fetchall()}

    if not relations:
        pytest.skip("analytics schema not built yet; run dbt build first")

    expected_tables = {
        "dim_customers",
        "dim_accounts",
        "dim_gl_accounts",
        "dim_date",
        "fct_transactions",
        "fct_ledger_entries",
        "fct_fee_assessments",
        "fct_fee_collections",
        "fct_customer_revenue",
    }
    expected_views = {
        "stg_gl_accounts",
        "stg_customers",
        "stg_accounts",
        "stg_overdraft_facilities",
        "stg_fx_rates",
        "stg_transactions",
        "stg_journals",
        "stg_ledger_entries",
        "stg_fee_assessments",
        "stg_fee_collections",
        "stg_revenue_recognitions",
        "stg_ingestion_batch_manifests",
        "int_customer_accounts",
        "int_transactions_enriched",
        "int_journal_balances",
        "int_fee_lifecycle",
        "int_customer_revenue",
    }

    for tbl in expected_tables:
        assert relations.get(tbl) == "BASE TABLE", f"Expected BASE TABLE analytics.{tbl}"

    for view in expected_views:
        assert relations.get(view) == "VIEW", f"Expected VIEW analytics.{view}"


def test_dbt_marts_financial_reconciliation(pg_conn: psycopg.Connection) -> None:
    """Verify key financial invariants across built dbt marts."""
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'analytics' AND table_name = 'fct_customer_revenue';
        """)
        if cur.fetchone()[0] == 0:
            pytest.skip("analytics.fct_customer_revenue not built yet")

        # 1. Zero unbalanced journals in int_journal_balances
        cur.execute("""
            SELECT COUNT(*)
            FROM analytics.int_journal_balances
            WHERE NOT is_balanced OR net_imbalance_amount <> 0.0000;
        """)
        assert cur.fetchone()[0] == 0

        # 2. Zero fan-out between fct_fee_assessments and fct_customer_revenue
        cur.execute("""
            SELECT
                (SELECT SUM(net_recognized_revenue_eur) FROM analytics.fct_fee_assessments),
                (SELECT SUM(net_recognized_revenue_eur) FROM analytics.fct_customer_revenue);
        """)
        fa_rev_eur, cr_rev_eur = cur.fetchone()
        assert fa_rev_eur is not None and cr_rev_eur is not None
        assert fa_rev_eur == cr_rev_eur
        assert fa_rev_eur > Decimal("0.0000")
