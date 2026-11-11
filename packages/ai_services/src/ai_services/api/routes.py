"""FastAPI endpoint routes for Governed Financial Analytics."""

from __future__ import annotations

import logging
from typing import Any, Literal

from ai_services.api.analytics_service import AnalyticsDataService
from ai_services.api.security import telemetry, verify_api_key
from ai_services.graph.workflow import build_financial_analytics_graph
from ai_services.schemas import (
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    BillingArrearsResponse,
    CustomerRankingsResponse,
    FinancialOverviewResponse,
    HealthResponse,
    RevenueTrendsResponse,
)
from data_platform.metadata.service import MetadataService
from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    environment: Literal["dev", "test"] = Query(
        default="dev", description="Database environment to probe"
    ),
) -> HealthResponse:
    """Probe system health and measure database connection latency under analytics_reader."""
    use_test_db = environment == "test"
    return AnalyticsDataService.get_health_probe(use_test_db=use_test_db)


@router.get("/overview", response_model=FinancialOverviewResponse)
def get_financial_overview(
    environment: Literal["dev", "test"] = Query(
        default="dev", description="Database environment: 'dev' or 'test'"
    ),
    _user: str | None = Depends(verify_api_key),
) -> FinancialOverviewResponse:
    """Fetch high-level executive financial metrics computed dynamically from analytical marts."""
    use_test_db = environment == "test"
    try:
        return AnalyticsDataService.get_financial_overview(use_test_db=use_test_db)
    except Exception as exc:
        logger.exception("Failed to retrieve financial overview: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load financial overview: {exc}",
        ) from exc


@router.get("/trends", response_model=RevenueTrendsResponse)
def get_revenue_trends(
    environment: Literal["dev", "test"] = Query(
        default="dev", description="Database environment: 'dev' or 'test'"
    ),
    _user: str | None = Depends(verify_api_key),
) -> RevenueTrendsResponse:
    """Fetch monthly revenue, assessed fee, and cash collection trends."""
    use_test_db = environment == "test"
    try:
        return AnalyticsDataService.get_monthly_trends(use_test_db=use_test_db)
    except Exception as exc:
        logger.exception("Failed to retrieve revenue trends: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load revenue trends: {exc}",
        ) from exc


@router.get("/customers", response_model=CustomerRankingsResponse)
def get_customer_rankings(
    environment: Literal["dev", "test"] = Query(
        default="dev", description="Database environment: 'dev' or 'test'"
    ),
    limit: int = Query(default=10, ge=1, le=100, description="Number of customers to return"),
    segment: str | None = Query(default=None, description="Filter by customer segment"),
    _user: str | None = Depends(verify_api_key),
) -> CustomerRankingsResponse:
    """Fetch customer leaderboard ranked by net recognized revenue."""
    use_test_db = environment == "test"
    try:
        return AnalyticsDataService.get_customer_rankings(
            use_test_db=use_test_db, limit=limit, segment=segment
        )
    except Exception as exc:
        logger.exception("Failed to retrieve customer rankings: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load customer rankings: {exc}",
        ) from exc


@router.get("/arrears", response_model=BillingArrearsResponse)
def get_billing_arrears(
    environment: Literal["dev", "test"] = Query(
        default="dev", description="Database environment: 'dev' or 'test'"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max exceptions to retrieve"),
    _user: str | None = Depends(verify_api_key),
) -> BillingArrearsResponse:
    """Fetch itemized billing exceptions and arrears breakdown."""
    use_test_db = environment == "test"
    try:
        return AnalyticsDataService.get_billing_arrears(use_test_db=use_test_db, limit=limit)
    except Exception as exc:
        logger.exception("Failed to retrieve billing arrears: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load billing arrears: {exc}",
        ) from exc


@router.post("/ask", response_model=AnalyticsQueryResponse)
def ask_analytics(
    request: AnalyticsQueryRequest,
    _user: str | None = Depends(verify_api_key),
) -> AnalyticsQueryResponse:
    """Submit a natural-language financial question and receive governed warehouse answer."""
    logger.info(
        "Received analytics question: '%s' (Env: %s, Trace: %s)",
        request.question,
        request.environment,
        request.conversation_id,
    )
    try:
        graph = build_financial_analytics_graph()
        result = graph.invoke(
            {
                "question": request.question,
                "environment": request.environment,
                "conversation_id": request.conversation_id,
            }
        )
        final_response = result.get("final_response")
        if not final_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Workflow completed without generating an answer.",
            )
        return final_response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error executing analytics workflow: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analytics workflow processing error: {exc}",
        ) from exc


@router.get("/telemetry")
def get_telemetry() -> dict[str, Any]:
    """Retrieve operational metrics snapshot (uptime, request counts, AI queries, latency)."""
    return telemetry.snapshot()


@router.get("/metrics")
def list_governed_metrics(_user: str | None = Depends(verify_api_key)) -> list[dict[str, Any]]:
    """List all certified financial metrics from the governance catalog."""
    meta = MetadataService()
    try:
        metrics = meta.list_metrics()
        return [m.model_dump() for m in metrics]
    except Exception as exc:
        logger.error("Failed retrieving metrics from catalog: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load governed metrics: {exc}",
        ) from exc


@router.get("/models")
def list_queryable_models(_user: str | None = Depends(verify_api_key)) -> list[dict[str, Any]]:
    """List all certified dimensional models authorized for AI inquiry."""
    meta = MetadataService()
    try:
        models = meta.list_queryable_models()
        return [m.model_dump() for m in models]
    except Exception as exc:
        logger.error("Failed retrieving queryable models: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load queryable models: {exc}",
        ) from exc
