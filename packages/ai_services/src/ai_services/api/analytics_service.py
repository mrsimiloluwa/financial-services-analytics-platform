"""Analytical service layer for querying governed financial marts.

Executes read-only analytical aggregations under least-privilege role
(analytics_reader) to power executive dashboards and API endpoints.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ai_services.schemas import (
    BillingArrearsItem,
    BillingArrearsResponse,
    CustomerRankingsResponse,
    CustomerRevenueRankingItem,
    FinancialOverviewResponse,
    HealthResponse,
    RevenueTrendItem,
    RevenueTrendsResponse,
)
from shared.config import get_settings
from shared.db import get_postgres_reader_connection

logger = logging.getLogger(__name__)


class AnalyticsDataService:
    """Service providing read-only executive metrics and marts aggregations."""

    @staticmethod
    def get_health_probe(use_test_db: bool = False) -> HealthResponse:
        """Measure database latency and probe read-only connectivity."""
        start_time = time.perf_counter()
        cfg = get_settings()
        db_status = "HEALTHY"
        latency_ms = None
        try:
            with (
                get_postgres_reader_connection(use_test_db=use_test_db) as conn,
                conn.cursor() as cur,
            ):
                cur.execute("SELECT 1;")
                cur.fetchone()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if cfg.is_duckdb:
                db_status = "HEALTHY (DuckDB In-Memory Marts)"
        except Exception as exc:
            logger.error("Health probe database error: %s", exc)
            db_status = f"UNHEALTHY: {exc}"

        status_code = "UP" if "HEALTHY" in db_status else "DEGRADED"
        db_comp = "duckdb" if cfg.is_duckdb else "postgresql"
        return HealthResponse(
            status=status_code,
            database=db_status,
            database_latency_ms=latency_ms,
            environment="test" if use_test_db else "dev",
            version="1.0.0",
            timestamp=datetime.now(UTC),
            components={
                db_comp: "UP" if "HEALTHY" in db_status else "DOWN",
                "analytics_reader": "UP" if "HEALTHY" in db_status else "DOWN",
                "metadata_service": "UP",
            },
        )

    @staticmethod
    def get_financial_overview(use_test_db: bool = False) -> FinancialOverviewResponse:
        """Fetch unified executive KPI metrics from fct_fee_assessments, fct_transactions, and dim_customers."""
        with (
            get_postgres_reader_connection(use_test_db=use_test_db) as conn,
            conn.cursor() as cur,
        ):
            # Aggregated fee assessments metrics
            cur.execute(
                """
                SELECT
                    ROUND(COALESCE(SUM(gross_assessed_amount_eur), 0)::numeric, 2) AS gross_assessed,
                    ROUND(COALESCE(SUM(waived_amount_eur), 0)::numeric, 2) AS waivers,
                    ROUND(COALESCE(SUM(net_collectible_amount_eur), 0)::numeric, 2) AS net_collectible,
                    ROUND(COALESCE(SUM(collected_amount_eur), 0)::numeric, 2) AS collected,
                    ROUND(COALESCE(SUM(outstanding_amount_eur), 0)::numeric, 2) AS arrears,
                    ROUND(COALESCE(SUM(pass_through_cost_eur), 0)::numeric, 2) AS pass_through,
                    ROUND(COALESCE(SUM(net_recognized_revenue_eur), 0)::numeric, 2) AS net_revenue,
                    COUNT(*) FILTER (WHERE outstanding_amount > 0) AS exception_count,
                    COUNT(DISTINCT customer_id) FILTER (WHERE outstanding_amount > 0) AS impacted_customers,
                    COUNT(*) AS total_assessments
                FROM analytics.fct_fee_assessments;
                """
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to compute fee assessments aggregations.")

            (
                gross_assessed,
                waivers,
                net_collectible,
                collected,
                arrears,
                pass_through,
                net_revenue,
                exception_count,
                impacted_customers,
                total_assessments,
            ) = row

            # Reversals from fct_customer_revenue
            cur.execute(
                """
                SELECT
                    ROUND(COALESCE(SUM(reversed_revenue_amount_eur), 0)::numeric, 2) AS reversals
                FROM analytics.fct_customer_revenue;
                """
            )
            rev_row = cur.fetchone()
            reversed_revenue = rev_row[0] if rev_row else Decimal("0.00")

            # Total active customers
            cur.execute("SELECT COUNT(*) FROM analytics.dim_customers;")
            total_customers_row = cur.fetchone()
            total_customers = total_customers_row[0] if total_customers_row else 0

            # Total transactions and gross volume
            cur.execute(
                """
                SELECT
                    COUNT(*),
                    ROUND(COALESCE(SUM(transaction_amount_eur), 0)::numeric, 2) AS gross_volume
                FROM analytics.fct_transactions;
                """
            )
            total_txns_row = cur.fetchone()
            total_txns = total_txns_row[0] if total_txns_row else 0
            gross_volume = total_txns_row[1] if total_txns_row else Decimal("0.00")

            # Realization percentages calculated via Decimal quantize (ROUND_HALF_UP)
            fee_coll_rate = (
                float(
                    ((collected / net_collectible) * Decimal("100")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                )
                if net_collectible and net_collectible > Decimal("0")
                else 0.0
            )
            take_rate = (
                float(
                    ((net_revenue / gross_assessed) * Decimal("100")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                )
                if gross_assessed and gross_assessed > Decimal("0")
                else 0.0
            )
            exception_rate = (
                float(
                    (
                        (Decimal(str(exception_count)) / Decimal(str(total_assessments)))
                        * Decimal("100")
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                )
                if total_assessments and total_assessments > 0
                else 0.0
            )
            volume_take_rate = (
                float(
                    ((net_revenue / gross_volume) * Decimal("10000")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                )
                if gross_volume and gross_volume > Decimal("0")
                else 0.0
            )

            return FinancialOverviewResponse(
                environment="test" if use_test_db else "dev",
                timestamp=datetime.now(UTC),
                net_recognized_revenue_eur=float(net_revenue or 0.0),
                gross_assessed_fees_eur=float(gross_assessed or 0.0),
                fee_waivers_eur=float(waivers or 0.0),
                net_collectible_fees_eur=float(net_collectible or 0.0),
                collected_fees_eur=float(collected or 0.0),
                uncollected_arrears_eur=float(arrears or 0.0),
                reversed_revenue_eur=float(reversed_revenue or 0.0),
                pass_through_costs_eur=float(pass_through or 0.0),
                gross_transaction_volume_eur=float(gross_volume or 0.0),
                fee_collection_rate_pct=fee_coll_rate,
                effective_take_rate_pct=take_rate,
                volume_take_rate_bps=volume_take_rate,
                billing_exception_rate_pct=exception_rate,
                total_exception_count=int(exception_count or 0),
                impacted_customers_count=int(impacted_customers or 0),
                total_customers_count=int(total_customers or 0),
                total_transactions_count=int(total_txns or 0),
                total_assessments_count=int(total_assessments or 0),
            )

    @staticmethod
    def get_monthly_trends(use_test_db: bool = False) -> RevenueTrendsResponse:
        """Fetch monthly aggregated revenue, assessed fees, and cash collections."""
        with (
            get_postgres_reader_connection(use_test_db=use_test_db) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT
                    TO_CHAR(assessed_month, 'YYYY-MM') AS month,
                    ROUND(COALESCE(SUM(net_recognized_revenue_eur), 0)::numeric, 2) AS net_revenue,
                    ROUND(COALESCE(SUM(gross_assessed_amount_eur), 0)::numeric, 2) AS gross_fees,
                    ROUND(COALESCE(SUM(collected_amount_eur), 0)::numeric, 2) AS collected_fees,
                    COUNT(*) AS assessments_count
                FROM analytics.fct_fee_assessments
                GROUP BY 1
                ORDER BY 1;
                """
            )
            rows = cur.fetchall()
            trends = [
                RevenueTrendItem(
                    month=r[0],
                    net_revenue_eur=float(r[1]),
                    gross_fees_eur=float(r[2]),
                    collected_fees_eur=float(r[3]),
                    assessments_count=int(r[4]),
                )
                for r in rows
            ]
            return RevenueTrendsResponse(
                environment="test" if use_test_db else "dev",
                trends=trends,
            )

    @staticmethod
    def get_customer_rankings(
        use_test_db: bool = False,
        limit: int = 10,
        segment: str | None = None,
    ) -> CustomerRankingsResponse:
        """Fetch customer leaderboard ranked by net recognized revenue."""
        with (
            get_postgres_reader_connection(use_test_db=use_test_db) as conn,
            conn.cursor() as cur,
        ):
            query = """
                SELECT
                    customer_id,
                    customer_name,
                    customer_segment,
                    ROUND(COALESCE(SUM(net_recognized_revenue_eur), 0)::numeric, 2) AS net_revenue,
                    ROUND(COALESCE(SUM(gross_assessed_fee_amount_eur), 0)::numeric, 2) AS gross_fees,
                    ROUND(COALESCE(SUM(collected_fee_amount_eur), 0)::numeric, 2) AS collected_fees,
                    ROUND(COALESCE(SUM(outstanding_fee_amount_eur), 0)::numeric, 2) AS arrears
                FROM analytics.fct_customer_revenue
            """
            params: list[Any] = []
            if segment:
                query += " WHERE customer_segment = %s"
                params.append(segment)

            query += " GROUP BY 1, 2, 3 ORDER BY net_revenue DESC LIMIT %s;"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

            customers = [
                CustomerRevenueRankingItem(
                    customer_id=r[0],
                    customer_name=r[1],
                    customer_segment=r[2],
                    net_revenue_eur=float(r[3]),
                    gross_fees_eur=float(r[4]),
                    collected_fees_eur=float(r[5]),
                    outstanding_arrears_eur=float(r[6]),
                )
                for r in rows
            ]
            return CustomerRankingsResponse(
                environment="test" if use_test_db else "dev",
                total_customers=len(customers),
                customers=customers,
            )

    @staticmethod
    def get_billing_arrears(
        use_test_db: bool = False,
        limit: int = 50,
    ) -> BillingArrearsResponse:
        """Fetch granular billing exceptions and arrears grouped by client, fee type, and currency."""
        with (
            get_postgres_reader_connection(use_test_db=use_test_db) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                SELECT
                    customer_id,
                    customer_name,
                    customer_segment,
                    fee_type,
                    currency,
                    COUNT(*) AS exception_count,
                    ROUND(COALESCE(SUM(outstanding_amount), 0)::numeric, 2) AS outstanding_native,
                    ROUND(COALESCE(SUM(outstanding_amount_eur), 0)::numeric, 2) AS outstanding_eur
                FROM analytics.fct_fee_assessments
                WHERE outstanding_amount > 0
                GROUP BY 1, 2, 3, 4, 5
                ORDER BY outstanding_eur DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

            exceptions = [
                BillingArrearsItem(
                    customer_id=r[0],
                    customer_name=r[1],
                    customer_segment=r[2],
                    fee_type=r[3],
                    currency=r[4],
                    exception_count=int(r[5]),
                    outstanding_native=float(r[6]),
                    outstanding_eur=float(r[7]),
                )
                for r in rows
            ]

            # Overall summary metrics for exceptions
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_exceptions,
                    ROUND(COALESCE(SUM(outstanding_amount_eur), 0)::numeric, 2) AS total_arrears,
                    COUNT(DISTINCT customer_id) AS impacted_customers
                FROM analytics.fct_fee_assessments
                WHERE outstanding_amount > 0;
                """
            )
            summary = cur.fetchone() or (0, Decimal("0.00"), 0)

            return BillingArrearsResponse(
                environment="test" if use_test_db else "dev",
                total_exception_count=int(summary[0]),
                total_arrears_eur=float(summary[1]),
                impacted_customers_count=int(summary[2]),
                exceptions=exceptions,
            )
