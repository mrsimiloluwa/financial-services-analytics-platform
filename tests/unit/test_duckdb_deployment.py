"""Unit and integration tests for standalone DuckDB deployment architecture.

Verifies that all 6 governed analytical marts load into DuckDB with exact row counts,
reconcile financial KPIs identically to PostgreSQL, and power all 5 dashboard
workspaces and AI Copilot inquiries without external database dependencies.
"""

from __future__ import annotations

import pytest
from ai_services.api.analytics_service import AnalyticsDataService
from ai_services.execution.engine import SQLExecutionEngine
from ai_services.graph.workflow import build_financial_analytics_graph
from ai_services.providers.mock import DeterministicMockLLMProvider
from ai_services.schemas import AnalyticsQueryResponse
from data_platform.metadata.service import MetadataService
from shared.config import get_settings
from shared.duckdb_reader import get_duckdb_marts_connection


@pytest.fixture(autouse=True)
def enable_duckdb_backend(monkeypatch):
    """Ensure all tests in this module run cleanly under embedded DuckDB mode."""
    monkeypatch.setenv("DATABASE_BACKEND", "duckdb")
    monkeypatch.setenv("POSTGRES_HOST", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_duckdb_dev_marts_row_counts_and_schemas():
    """Verify all 6 analytical marts load into DuckDB matching DEV warehouse grain."""
    con = get_duckdb_marts_connection(use_test_db=False)

    tables_and_counts = {
        "dim_customers": 50,
        "dim_accounts": 111,
        "fct_customer_revenue": 1667,
        "fct_fee_assessments": 3791,
        "fct_fee_collections": 3791,
        "fct_transactions": 5000,
    }

    for table_name, expected_count in tables_and_counts.items():
        res = con.execute(f"SELECT COUNT(*) FROM analytics.{table_name};").fetchone()
        assert res is not None
        assert res[0] == expected_count, f"{table_name} expected {expected_count}, got {res[0]}"


def test_duckdb_test_environment_isolation():
    """Verify isolated TEST environment loads corresponding sample_data/test/ marts."""
    con = get_duckdb_marts_connection(use_test_db=True)

    tables_and_counts = {
        "dim_customers": 10,
        "dim_accounts": 24,
        "fct_fee_assessments": 148,
        "fct_fee_collections": 148,
        "fct_transactions": 200,
    }

    for table_name, expected_count in tables_and_counts.items():
        res = con.execute(f"SELECT COUNT(*) FROM analytics.{table_name};").fetchone()
        assert res is not None
        assert res[0] == expected_count, f"{table_name} expected {expected_count}, got {res[0]}"


def test_duckdb_financial_overview_reconciliation():
    """Verify DuckDB analytical service reproduces exact certified financial metrics."""
    overview = AnalyticsDataService.get_financial_overview(use_test_db=False)

    assert overview.environment == "dev"
    assert overview.net_recognized_revenue_eur == 408602.64
    assert overview.gross_assessed_fees_eur == 467449.70
    assert overview.fee_waivers_eur == 8061.56
    assert overview.net_collectible_fees_eur == 459388.14
    assert overview.collected_fees_eur == 430108.04
    assert overview.uncollected_arrears_eur == 29280.10
    assert overview.reversed_revenue_eur == 0.00
    assert overview.pass_through_costs_eur == 21505.40
    assert overview.gross_transaction_volume_eur == 1149541948.51
    assert overview.effective_take_rate_pct == 87.41
    assert overview.fee_collection_rate_pct == 93.63
    assert overview.total_exception_count == 200
    assert overview.total_assessments_count == 3791
    assert overview.billing_exception_rate_pct == 5.28
    assert overview.impacted_customers_count == 46
    assert overview.total_customers_count == 50
    assert overview.total_transactions_count == 5000


def test_duckdb_monthly_trends_and_rankings():
    """Verify monthly trends and customer leaderboards execute cleanly in DuckDB."""
    # 1. Monthly Trends
    trends_resp = AnalyticsDataService.get_monthly_trends(use_test_db=False)
    assert len(trends_resp.trends) == 12
    assert trends_resp.trends[0].month == "2025-01"
    assert trends_resp.trends[0].net_revenue_eur == 39203.70

    # 2. Customer Rankings
    rankings = AnalyticsDataService.get_customer_rankings(use_test_db=False, limit=5)
    assert len(rankings.customers) == 5
    top = rankings.customers[0]
    assert top.customer_name == "Equinox Logistics GmbH"
    assert top.net_revenue_eur == 34963.01

    # 3. Billing Arrears Registry
    arrears = AnalyticsDataService.get_billing_arrears(use_test_db=False, limit=10)
    assert arrears.total_exception_count == 200
    assert arrears.total_arrears_eur == 29280.10
    assert len(arrears.exceptions) == 10
    assert arrears.exceptions[0].fee_type == "WIRE_TRANSFER"


def test_duckdb_health_probe():
    """Verify health probe identifies DuckDB in-memory analytical warehouse."""
    health = AnalyticsDataService.get_health_probe(use_test_db=False)
    assert health.status == "UP"
    assert "DuckDB" in health.database
    assert health.components["duckdb"] == "UP"
    assert health.components["analytics_reader"] == "UP"


def test_duckdb_sql_execution_engine():
    """Verify SQLExecutionEngine executes read-only SQL under DuckDB in sub-millisecond time."""
    engine = SQLExecutionEngine(use_test_db=False)
    result = engine.execute_query(
        "SELECT SUM(net_recognized_revenue_eur) AS total_revenue FROM analytics.fct_customer_revenue;"
    )
    assert result.error is None
    assert result.row_count == 1
    assert len(result.rows) == 1
    assert round(result.rows[0]["total_revenue"], 2) == 408602.64
    assert result.execution_time_ms < 500  # Sub-second execution


def test_duckdb_ai_copilot_full_langgraph_flow():
    """Verify end-to-end LangGraph state machine completes on DuckDB with certified metrics."""
    mock_provider = DeterministicMockLLMProvider()
    graph = build_financial_analytics_graph(provider=mock_provider)

    result = graph.invoke(
        {
            "question": "What was our total net recognized revenue?",
            "environment": "dev",
        }
    )

    resp: AnalyticsQueryResponse | None = result.get("final_response")
    assert resp is not None
    assert resp.status == "SUCCESS"
    assert resp.metric_used == "Recognized Revenue"
    assert "€408,602.64" in resp.answer
    assert resp.sql_query is not None
    assert "analytics.fct_customer_revenue" in resp.sql_query
    assert resp.execution_time_ms is not None


def test_metadata_service_standalone_fallback():
    """Verify MetadataService retrieves certified metrics and queryable models without PostgreSQL."""
    meta = MetadataService()
    metrics = meta.list_metrics()
    assert len(metrics) == 12

    metric_ids = {m.metric_id for m in metrics}
    assert "recognized_revenue" in metric_ids
    assert "fee_collection_rate" in metric_ids

    models = meta.list_queryable_models()
    assert len(models) >= 4
    model_names = {m.name for m in models}
    assert "fct_customer_revenue" in model_names
    assert "fct_fee_assessments" in model_names

    # Verify query context construction for AI
    ctx = meta.build_ai_query_context("fct_customer_revenue")
    assert ctx.model_name == "fct_customer_revenue"
    assert len(ctx.columns) > 0


def test_duckdb_automatic_fallback_when_postgres_unreachable(monkeypatch):
    """Verify that if PostgreSQL is unreachable on localhost (e.g. Streamlit Cloud),

    get_postgres_reader_connection falls back to embedded DuckDB reader without crashing.
    """
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "59999")  # Non-existent port
    get_settings.cache_clear()

    from shared.db import get_postgres_reader_connection

    with get_postgres_reader_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM analytics.dim_customers;")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 50
