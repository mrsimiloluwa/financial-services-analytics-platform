"""FastAPI application factory for AI Financial Analytics service."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from ai_services.api.analytics_service import AnalyticsDataService
from ai_services.api.routes import router as analytics_router
from ai_services.api.security import rate_limiter, telemetry
from ai_services.schemas import ErrorResponse, HealthResponse
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    app = FastAPI(
        title="Enterprise AI Analytics Platform — Financial Services API",
        description=(
            "Governed AI analytics API for commercial banking revenue, transactions, fee lifecycle, "
            "and portfolio performance. Integrates LangGraph, SQLGlot validation, and dbt metadata catalog."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable CORS for local development and Streamlit frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_and_observability_middleware(request: Request, call_next):
        """Enforce rate limits, inject correlation ID, collect telemetry, and apply secure headers."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        client_ip = request.client.host if request.client else "127.0.0.1"

        # Rate limiting check (exempting health and documentation paths)
        path = request.url.path
        is_exempt = path in ("/health", "/", "/docs", "/redoc", "/openapi.json") or path.endswith(
            "/health"
        )
        if not is_exempt and not rate_limiter.check(client_ip):
            logger.warning("Rate limit exceeded for client IP: %s on path %s", client_ip, path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=ErrorResponse(
                    error="TooManyRequests",
                    detail="API request rate limit exceeded. Please retry in 60 seconds.",
                    error_code="RATE_LIMIT_EXCEEDED",
                    timestamp=datetime.now(UTC),
                    request_id=request_id,
                ).model_dump(mode="json"),
                headers={"Retry-After": "60", "X-Request-ID": request_id},
            )

        start_time = time.perf_counter()
        is_error = False
        try:
            response = await call_next(request)
            if response.status_code >= 500:
                is_error = True
        except Exception:
            is_error = True
            raise
        finally:
            process_time_ms = (time.perf_counter() - start_time) * 1000
            is_ai = "/ask" in path
            telemetry.record_request(latency_ms=process_time_ms, is_ai=is_ai, is_error=is_error)

        # Response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Ensure unhandled exceptions return a standardized JSON error response."""
        request_id = request.headers.get("X-Request-ID", "unknown")
        logger.exception("Unhandled server error processing %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="InternalServerError",
                detail=str(exc),
                error_code="INTERNAL_ERROR",
                timestamp=datetime.now(UTC),
                request_id=request_id,
            ).model_dump(mode="json"),
        )

    # Root and Observability Endpoints
    @app.get("/", tags=["system"])
    def root():
        """Service identity and status."""
        return {
            "name": "Enterprise AI Analytics Platform — Financial Services API",
            "version": "1.0.0",
            "status": "ONLINE",
            "docs": "/docs",
            "governed_marts": [
                "dim_accounts",
                "dim_customers",
                "fct_customer_revenue",
                "fct_fee_assessments",
                "fct_fee_collections",
                "fct_transactions",
            ],
        }

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def root_health():
        """Root health probe for container orchestration."""
        return AnalyticsDataService.get_health_probe(use_test_db=False)

    @app.get("/telemetry", tags=["system"])
    def root_telemetry():
        """Operational metrics snapshot (uptime, request counts, AI queries, latency)."""
        return telemetry.snapshot()

    app.include_router(analytics_router)

    return app


app = create_app()
