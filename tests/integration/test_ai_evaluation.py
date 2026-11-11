"""Integration tests for AI evaluation benchmark suite, financial grounding, and error handling."""

from __future__ import annotations

import pytest
from ai_services.eval.evaluator import AIAnalyticsEvaluator
from ai_services.graph.workflow import build_financial_analytics_graph
from ai_services.providers.mock import DeterministicMockLLMProvider


@pytest.fixture
def mock_evaluator() -> AIAnalyticsEvaluator:
    return AIAnalyticsEvaluator(
        provider=DeterministicMockLLMProvider(),
        environment="test",
    )


def test_full_evaluation_benchmark_suite(mock_evaluator: AIAnalyticsEvaluator):
    """Run complete 32-case curated financial benchmark suite with DeterministicMockLLMProvider."""
    summary = mock_evaluator.run_suite()

    # Assert 100% security boundary defense
    assert summary.security_defense_pct == 100.0, (
        f"Security defense compromised: {summary.security_defense_pct}%"
    )

    # Assert aggregate benchmark accuracy exceeds 95%
    assert summary.accuracy_pct >= 95.0, (
        f"Benchmark accuracy too low: {summary.accuracy_pct}% ({summary.passed_cases}/{summary.total_cases})"
    )

    # Assert every individual category achieved >= 90%
    for category, score in summary.category_scores.items():
        assert score >= 90.0, f"Category '{category}' failed minimum threshold: {score}%"


def test_grounded_financial_numbers():
    """Verify that numbers emitted in the answer narrative match actual query result data."""
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    result = graph.invoke(
        {
            "question": "What was our total net recognized revenue?",
            "environment": "test",
        }
    )
    resp = result["final_response"]
    assert resp.status == "SUCCESS"
    assert resp.data is not None and len(resp.data) > 0

    # Extract actual net revenue from returned warehouse data
    actual_net_rev = float(resp.data[0]["net_recognized_revenue_eur"])
    expected_formatted_str = f"€{actual_net_rev:,.2f}"

    # Assert that the exact formatted number is present in the narrative
    assert expected_formatted_str in resp.answer, (
        f"Answer narrative '{resp.answer}' does not ground to returned warehouse figure '{expected_formatted_str}'"
    )

    # Assert no claims of IFRS 15 or audited ECB rates
    assert "IFRS 15" not in resp.answer
    assert "audited daily ECB" not in resp.answer


def test_revenue_reconciliation_bridge():
    """Verify the arithmetic reconciliation bridge between gross assessed fees, waivers, arrears, pass-through costs, and net revenue."""
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    result = graph.invoke(
        {
            "question": "What was our total net recognized revenue?",
            "environment": "dev",
        }
    )
    resp = result["final_response"]
    assert resp.status == "SUCCESS"
    assert resp.data is not None and len(resp.data) > 0
    row = resp.data[0]

    gross = float(row["gross_assessed_fee_amount_eur"])
    waived = float(row["waived_fee_amount_eur"])
    net_collectible = float(row["net_collectible_fee_amount_eur"])
    collected = float(row["collected_fee_amount_eur"])
    arrears = float(row["outstanding_fee_amount_eur"])
    reversals = float(row.get("reversed_revenue_amount_eur", 0.0))
    pass_through = float(row["pass_through_cost_amount_eur"])
    net_rev = float(row["net_recognized_revenue_eur"])

    # 1. Verify mathematical integrity of warehouse data
    assert round(gross - waived, 2) == round(net_collectible, 2)
    assert round(net_collectible - arrears, 2) == round(collected, 2)
    assert round(collected - pass_through, 2) == round(net_rev, 2)

    # 2. Reconcile the exact difference between net collectible and net recognized revenue
    reconciliation_gap = round(net_collectible - net_rev, 2)
    expected_gap = round(arrears + pass_through, 2)
    assert reconciliation_gap == expected_gap == 50785.50

    # 3. Assert answer narrative explicitly explains the reconciliation bridge
    assert f"€{gross:,.2f}" in resp.answer
    assert f"€{waived:,.2f}" in resp.answer
    assert f"€{net_collectible:,.2f}" in resp.answer
    assert f"€{arrears:,.2f}" in resp.answer
    assert f"€{reversals:,.2f}" in resp.answer
    assert f"€{pass_through:,.2f}" in resp.answer
    assert f"€{net_rev:,.2f}" in resp.answer
    assert f"€{reconciliation_gap:,.2f}" in resp.answer


def test_outstanding_arrears_currency_and_count_grounding():
    """Verify that portfolio exception inquiries use EUR conversion and report true assessment and client counts."""
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    result = graph.invoke(
        {
            "question": "Are there outstanding fees that need attention?",
            "environment": "dev",
        }
    )
    resp = result["final_response"]
    assert resp.status == "SUCCESS"
    assert resp.data is not None and len(resp.data) > 0
    row = resp.data[0]

    # Verify query used EUR converted values
    assert "outstanding_amount_eur" in resp.sql_query
    assert "total_exception_count" in row
    assert "impacted_customers_count" in row
    assert "total_arrears_eur" in row
    assert "total_assessment_count" in row

    # Assert exact DEV counts
    assert int(row["total_exception_count"]) == 200
    assert int(row["impacted_customers_count"]) == 46
    assert round(float(row["total_arrears_eur"]), 2) == 29280.10
    assert int(row["total_assessment_count"]) == 3791
    assert float(row["billing_exception_rate_pct"]) == 5.28

    # Assert answer narrative states these figures correctly
    assert "200 billing exception assessments" in resp.answer
    assert "46 commercial clients" in resp.answer
    assert "€29,280.10" in resp.answer
    assert "5.28%" in resp.answer
    assert "3,791 total fee assessments" in resp.answer


def test_billing_exception_rate_denominator_and_uniqueness():
    """Verify that the billing exception rate denominator is exactly total fee assessments with 1:1 grain uniqueness."""
    from shared.db import get_postgres_connection

    with get_postgres_connection() as conn, conn.cursor() as cur:
        # Verify 100% grain uniqueness on assessment_id in fct_fee_assessments
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT assessment_id) AS distinct_assessments
            FROM analytics.fct_fee_assessments;
            """
        )
        total_rows, distinct_assessments = cur.fetchone()
        assert total_rows == distinct_assessments == 3791, (
            f"Fanout or duplicate records detected in fct_fee_assessments: {total_rows} rows vs {distinct_assessments} distinct keys"
        )

        # Verify raw.fee_assessments matches fct_fee_assessments exactly
        cur.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT assessment_id)
            FROM raw.fee_assessments;
            """
        )
        raw_rows, raw_distinct = cur.fetchone()
        assert raw_rows == raw_distinct == 3791, "raw.fee_assessments does not match mart grain"

        # Verify numerator, denominator, and exact rate calculation
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE outstanding_amount > 0) AS exceptions_numerator,
                COUNT(*) AS total_denominator,
                ROUND((COUNT(*) FILTER (WHERE outstanding_amount > 0)::float / NULLIF(COUNT(*), 0) * 100)::numeric, 2) AS exact_rate_pct
            FROM analytics.fct_fee_assessments;
            """
        )
        numerator, denominator, exact_rate = cur.fetchone()
        assert numerator == 200
        assert denominator == 3791
        assert float(exact_rate) == 5.28

        # Confirm why 3.85% was erroneous (it divided 200 by ~5,200 instead of the true 3,791 denominator)
        erroneous_rate = round(200.0 / 5195.0 * 100, 2)
        assert erroneous_rate == 3.85
        assert float(exact_rate) != erroneous_rate


def test_customer_arrears_breakdown_distinguishes_segments_from_assessments():
    """Verify that grouped customer arrears breakdown explicitly distinguishes grouped segments from individual assessments."""
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    result = graph.invoke(
        {
            "question": "Show me uncollected fee arrears by customer",
            "environment": "dev",
        }
    )
    resp = result["final_response"]
    assert resp.status == "SUCCESS"
    assert resp.data is not None and len(resp.data) > 0

    # Verify SQL uses outstanding_amount_eur (no mixed native currency aggregation)
    assert "SUM(outstanding_amount_eur)" in resp.sql_query
    assert "GROUP BY customer_name, customer_segment, fee_type, currency" in resp.sql_query

    # Verify narrative explicitly mentions grouped segments vs assessments
    assert "grouped client/product exposure segments" in resp.answer
    assert "individual fee assessments" in resp.answer
    assert "EUR-converted arrears" in resp.answer


def test_unsupported_questions():
    """Verify that non-banking and unsupported analytical requests are gracefully rejected as OUT_OF_SCOPE."""
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    unsupported = [
        "What is the weather forecast for tomorrow?",
        "Can you write a poem about banking?",
        "How do I bake a chocolate cake?",
        "Who won the chess championship?",
    ]
    for q in unsupported:
        result = graph.invoke({"question": q, "environment": "test"})
        resp = result["final_response"]
        assert resp.status == "OUT_OF_SCOPE", (
            f"Query '{q}' expected OUT_OF_SCOPE, got {resp.status}"
        )
        assert resp.sql_query is None


def test_ambiguous_metrics():
    """Verify that vaguely worded inquiries resolve to default valid mart models rather than failing."""
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    result = graph.invoke(
        {
            "question": "Can you give me an overview of financial figures?",
            "environment": "test",
        }
    )
    resp = result["final_response"]
    assert resp.status == "SUCCESS"
    assert resp.model_used in ["fct_customer_revenue", "fct_transactions", "fct_fee_assessments"]
