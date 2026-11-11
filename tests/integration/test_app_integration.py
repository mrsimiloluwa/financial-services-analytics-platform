"""Integration tests for Phase 6 Application Engineering & Productisation.

Exercises FastAPI endpoints and AnalyticsDataService across DEV and TEST databases.
Verifies data contracts, environment isolation, customer rankings, monthly trends,
and billing arrears reconciliation.
"""

from __future__ import annotations

import pytest
from ai_services.api.analytics_service import AnalyticsDataService
from ai_services.api.app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_overview_dev_vs_test_isolation(client: TestClient):
    """Verify financial overview reflects live warehouse data with strict DEV/TEST separation."""
    # 1. DEV Showcase Database
    res_dev = client.get("/api/v1/analytics/overview?environment=dev")
    assert res_dev.status_code == 200
    data_dev = res_dev.json()

    assert data_dev["environment"] == "dev"
    assert data_dev["net_recognized_revenue_eur"] == 408602.64
    assert data_dev["gross_assessed_fees_eur"] == 467449.70
    assert data_dev["fee_waivers_eur"] == 8061.56
    assert data_dev["net_collectible_fees_eur"] == 459388.14
    assert data_dev["collected_fees_eur"] == 430108.04
    assert data_dev["uncollected_arrears_eur"] == 29280.10
    assert data_dev["reversed_revenue_eur"] == 0.00
    assert data_dev["pass_through_costs_eur"] == 21505.40
    assert data_dev["gross_transaction_volume_eur"] == 1149541948.51
    assert data_dev["effective_take_rate_pct"] == 87.41
    assert data_dev["volume_take_rate_bps"] == 3.55
    assert data_dev["fee_collection_rate_pct"] == 93.63
    assert data_dev["total_exception_count"] == 200
    assert data_dev["total_assessments_count"] == 3791
    assert data_dev["billing_exception_rate_pct"] == 5.28
    assert data_dev["impacted_customers_count"] == 46
    assert data_dev["total_customers_count"] == 50
    assert data_dev["total_transactions_count"] == 5000

    # 2. TEST Isolation Database
    res_test = client.get("/api/v1/analytics/overview?environment=test")
    assert res_test.status_code == 200
    data_test = res_test.json()

    assert data_test["environment"] == "test"
    assert data_test["net_recognized_revenue_eur"] in (17042.01, 17132.40)
    assert data_test["total_exception_count"] in (1, 8)
    assert data_test["total_assessments_count"] == 148
    assert data_test["total_customers_count"] == 10
    assert data_test["total_transactions_count"] == 200

    # Confirm isolation
    assert data_dev["net_recognized_revenue_eur"] != data_test["net_recognized_revenue_eur"]
    assert data_dev["total_customers_count"] > data_test["total_customers_count"]


def test_api_revenue_trends(client: TestClient):
    """Verify monthly revenue trends endpoint aggregates 12 months correctly."""
    response = client.get("/api/v1/analytics/trends?environment=dev")
    assert response.status_code == 200
    data = response.json()

    assert data["environment"] == "dev"
    assert len(data["trends"]) == 12

    first_month = data["trends"][0]
    assert first_month["month"] == "2025-01"
    assert first_month["net_revenue_eur"] > 0
    assert first_month["gross_fees_eur"] > 0
    assert first_month["collected_fees_eur"] > 0
    assert first_month["assessments_count"] > 0


def test_api_customer_rankings_and_filtering(client: TestClient):
    """Verify customer ranking leaderboard and segment filtering."""
    # Top 5 overall
    res_top5 = client.get("/api/v1/analytics/customers?environment=dev&limit=5")
    assert res_top5.status_code == 200
    data_top5 = res_top5.json()

    assert data_top5["total_customers"] == 5
    cust_names = [c["customer_name"] for c in data_top5["customers"]]
    assert "Equinox Logistics GmbH" in cust_names

    # Filter by segment
    res_sme = client.get(
        "/api/v1/analytics/customers?environment=dev&limit=5&segment=COMMERCIAL_SME"
    )
    assert res_sme.status_code == 200
    data_sme = res_sme.json()
    for c in data_sme["customers"]:
        assert c["customer_segment"] == "COMMERCIAL_SME"


def test_api_billing_arrears(client: TestClient):
    """Verify billing arrears registry returns correct total and itemized exceptions."""
    response = client.get("/api/v1/analytics/arrears?environment=dev&limit=10")
    assert response.status_code == 200
    data = response.json()

    assert data["environment"] == "dev"
    assert data["total_exception_count"] == 200
    assert data["total_arrears_eur"] == 29280.10
    assert data["impacted_customers_count"] == 46
    assert len(data["exceptions"]) == 10

    first_exception = data["exceptions"][0]
    assert first_exception["outstanding_eur"] > 0
    assert first_exception["customer_name"] is not None
    assert first_exception["currency"] in ("EUR", "USD", "GBP")


def test_api_ask_live_financial_answer(client: TestClient):
    """Verify natural-language inquiry against live DEV database."""
    payload = {
        "question": "What was our total net recognized revenue?",
        "environment": "dev",
    }
    response = client.post("/api/v1/analytics/ask", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert "408,602.64" in data["answer"]
    assert "recognized" in data["metric_used"].lower()
    assert data["model_used"] == "fct_customer_revenue"
    assert data["sql_query"] is not None
    assert len(data["data"]) == 1
    assert data["execution_time_ms"] > 0


def test_service_health_probe_latency():
    """Verify AnalyticsDataService direct health probe reports latency and UP status."""
    probe = AnalyticsDataService.get_health_probe(use_test_db=False)
    assert probe.status == "UP"
    assert "HEALTHY" in probe.database
    assert probe.database_latency_ms is not None
    assert probe.database_latency_ms > 0
    db_comp = "duckdb" if "duckdb" in probe.components else "postgresql"
    assert probe.components[db_comp] == "UP"


def test_analytics_reader_least_privilege_post_dbt_build():
    """Assert analytics_reader maintains strict least-privilege boundary after dbt model rebuilds."""
    from shared.config import get_settings

    if get_settings().is_duckdb:
        pytest.skip("PostgreSQL role permission tests require live PostgreSQL warehouse")

    import psycopg
    from shared.db import get_postgres_reader_connection

    with get_postgres_reader_connection() as conn, conn.cursor() as cur:
        # 1. Allowed: Exactly the 6 approved dimensional marts
        approved_marts = [
            "dim_accounts",
            "dim_customers",
            "fct_customer_revenue",
            "fct_fee_assessments",
            "fct_fee_collections",
            "fct_transactions",
        ]
        for mart in approved_marts:
            cur.execute(f"SELECT COUNT(*) FROM analytics.{mart};")
            res = cur.fetchone()
            assert res is not None and res[0] >= 0

        # 2. Denied: raw schema access
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT COUNT(*) FROM raw.customers;")

        # 3. Denied: metadata catalog access
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT COUNT(*) FROM metadata.model_catalog;")

        # 4. Denied: DML operations
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(
                "DELETE FROM analytics.fct_customer_revenue WHERE customer_id = 'CUST_9999';"
            )
