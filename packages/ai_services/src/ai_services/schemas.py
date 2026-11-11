"""Pydantic schemas and typed data contracts for AI Financial Analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyticsQueryRequest(BaseModel):
    """User-facing natural language financial inquiry request."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Financial question in plain English.",
        examples=["What was our total net recognized revenue?"],
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation trace ID for audit logging.",
        examples=["conv_2026_01"],
    )
    environment: Literal["dev", "test"] = Field(
        default="dev",
        description="Target warehouse environment: 'dev' (showcase) or 'test' (isolation).",
    )


class QuestionUnderstanding(BaseModel):
    """Structured intent and entity decomposition extracted from the inquiry."""

    intent: str
    entities: dict[str, Any] = Field(default_factory=dict)
    time_period: str | None = None
    is_out_of_scope: bool = False
    rejection_reason: str | None = None


class MetricResolution(BaseModel):
    """Resolved governed financial metric and primary source model."""

    metric_id: str | None = None
    metric_name: str | None = None
    source_model: str | None = None
    formula: str | None = None
    confidence: float = 1.0


class SQLValidationResult(BaseModel):
    """Outcome of SQLGlot security and boundary validation."""

    is_valid: bool
    sanitized_sql: str | None = None
    error_message: str | None = None
    tables_accessed: list[str] = Field(default_factory=list)
    columns_accessed: list[str] = Field(default_factory=list)


class QueryResult(BaseModel):
    """Structured result set returned by read-only warehouse execution."""

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    truncated: bool = False
    error: str | None = None


class AnalyticsQueryResponse(BaseModel):
    """Unified user-facing response package containing narrative answer and evidence."""

    question: str
    answer: str
    metric_used: str | None = None
    model_used: str | None = None
    sql_query: str | None = None
    data: list[dict[str, Any]] | None = None
    columns: list[str] | None = None
    row_count: int | None = None
    execution_time_ms: float | None = None
    currency: str | None = "EUR"
    reporting_period: str | None = None
    confidence: float = 1.0
    limitations: str | None = None
    status: Literal["SUCCESS", "REJECTED", "ERROR", "OUT_OF_SCOPE"] = "SUCCESS"


# --- Executive Dashboard & API V1 Response Models ---


class FinancialOverviewResponse(BaseModel):
    """High-level executive financial metrics computed dynamically from the analytical warehouse."""

    environment: str = Field(..., description="Target database environment (dev or test)")
    timestamp: datetime = Field(..., description="UTC timestamp of overview generation")
    net_recognized_revenue_eur: float = Field(..., description="Net recognized revenue in EUR")
    gross_assessed_fees_eur: float = Field(..., description="Gross fees assessed in EUR")
    fee_waivers_eur: float = Field(..., description="Fee waivers granted in EUR")
    net_collectible_fees_eur: float = Field(
        ..., description="Net collectible fees (gross - waivers) in EUR"
    )
    collected_fees_eur: float = Field(..., description="Collected fee cash in EUR")
    uncollected_arrears_eur: float = Field(
        ..., description="Total outstanding fees (arrears) in EUR"
    )
    reversed_revenue_eur: float = Field(
        default=0.0, description="Gross collected fee revenue reversals in EUR"
    )
    pass_through_costs_eur: float = Field(
        ..., description="Interchange and pass-through costs in EUR"
    )
    gross_transaction_volume_eur: float = Field(
        default=0.0, description="Total gross commercial transaction volume in EUR"
    )
    fee_collection_rate_pct: float = Field(
        ...,
        description="Fee collection realization rate percentage: (Collected / Net Collectible) * 100",
    )
    effective_take_rate_pct: float = Field(
        ...,
        description="Effective Fee Realization Rate percentage: (Net Recognized Revenue / Gross Assessed Fees) * 100",
    )
    volume_take_rate_bps: float = Field(
        default=0.0,
        description="Commercial Volume Take Rate in basis points: (Net Revenue / Gross Volume) * 10,000",
    )
    billing_exception_rate_pct: float = Field(
        ..., description="Billing exception percentage (exceptions / total assessments)"
    )
    total_exception_count: int = Field(..., description="Count of fee assessments in arrears")
    impacted_customers_count: int = Field(
        ..., description="Count of distinct customers with arrears"
    )
    total_customers_count: int = Field(..., description="Count of distinct active customers")
    total_transactions_count: int = Field(..., description="Total commercial transaction count")
    total_assessments_count: int = Field(..., description="Total fee assessment count")


class RevenueTrendItem(BaseModel):
    """Monthly financial performance aggregated across marts."""

    month: str = Field(..., description="Year-month formatted as YYYY-MM")
    net_revenue_eur: float = Field(..., description="Net recognized revenue in EUR")
    gross_fees_eur: float = Field(..., description="Gross fees assessed in EUR")
    collected_fees_eur: float = Field(..., description="Collected fees in EUR")
    assessments_count: int = Field(..., description="Count of fee assessments in month")


class RevenueTrendsResponse(BaseModel):
    """Timeseries collection of monthly financial performance."""

    environment: str
    trends: list[RevenueTrendItem]


class CustomerRevenueRankingItem(BaseModel):
    """Customer-level revenue, fee contribution, and arrears summary."""

    customer_id: str
    customer_name: str
    customer_segment: str
    net_revenue_eur: float
    gross_fees_eur: float
    collected_fees_eur: float
    outstanding_arrears_eur: float


class CustomerRankingsResponse(BaseModel):
    """Collection of ranked customers by revenue."""

    environment: str
    total_customers: int
    customers: list[CustomerRevenueRankingItem]


class BillingArrearsItem(BaseModel):
    """Itemized billing exception aggregated by customer and fee category."""

    customer_id: str
    customer_name: str
    customer_segment: str
    fee_type: str
    currency: str
    exception_count: int
    outstanding_native: float
    outstanding_eur: float


class BillingArrearsResponse(BaseModel):
    """Executive billing arrears and exceptions registry."""

    environment: str
    total_exception_count: int
    total_arrears_eur: float
    impacted_customers_count: int
    exceptions: list[BillingArrearsItem]


class HealthResponse(BaseModel):
    """Structured system and database connectivity health probe."""

    status: Literal["UP", "DEGRADED", "DOWN"]
    database: str
    database_latency_ms: float | None = None
    environment: str
    version: str
    timestamp: datetime
    components: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standardized API error envelope for client consumption."""

    error: str
    detail: str
    error_code: str
    timestamp: datetime
    request_id: str | None = None
