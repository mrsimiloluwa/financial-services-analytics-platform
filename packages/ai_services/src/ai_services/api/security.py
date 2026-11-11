"""Application security, authentication, rate limiting, and telemetry monitoring."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from shared.config import Settings, get_settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class RateLimiter:
    """Sliding-window in-memory request rate limiter."""

    def __init__(self, requests_per_minute: int = 120) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def check(self, client_ip: str) -> bool:
        """Return True if request is within limits, False if exceeded."""
        now = time.time()
        window_start = now - 60.0

        with self.lock:
            # Prune timestamps older than 60 seconds
            self.requests[client_ip] = [ts for ts in self.requests[client_ip] if ts > window_start]
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                return False
            self.requests[client_ip].append(now)
            return True


@dataclass
class TelemetryStats:
    """Operational metrics tracked in memory."""

    start_time: float = field(default_factory=time.time)
    total_requests: int = 0
    total_ai_queries: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    lock: Lock = field(default_factory=Lock)

    def record_request(self, latency_ms: float, is_ai: bool = False, is_error: bool = False):
        with self.lock:
            self.total_requests += 1
            self.total_latency_ms += latency_ms
            if is_ai:
                self.total_ai_queries += 1
            if is_error:
                self.total_errors += 1

    def snapshot(self) -> dict:
        with self.lock:
            uptime = round(time.time() - self.start_time, 1)
            avg_lat = (
                round(self.total_latency_ms / self.total_requests, 2)
                if self.total_requests > 0
                else 0.0
            )
            return {
                "uptime_seconds": uptime,
                "total_requests": self.total_requests,
                "total_ai_queries": self.total_ai_queries,
                "total_errors": self.total_errors,
                "average_latency_ms": avg_lat,
                "timestamp": datetime.now(UTC).isoformat(),
            }


telemetry = TelemetryStats()
rate_limiter = RateLimiter()


def verify_api_key(
    request: Request,
    api_key: Annotated[str | None, Security(api_key_header)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> str | None:
    """Validate API key when authentication is enabled in application settings."""
    cfg = settings or get_settings()

    if not cfg.api_auth_enabled:
        return "ANONYMOUS_DEV"

    # Allow Bearer token in Authorization header as alternative
    auth_header = request.headers.get("Authorization")
    extracted_key = api_key
    if not extracted_key and auth_header and auth_header.startswith("Bearer "):
        extracted_key = auth_header.split(" ", 1)[1]

    expected_key = cfg.api_key
    if not extracted_key or (expected_key and extracted_key != expected_key):
        logger.warning(
            "Unauthorized API access attempt from %s for %s",
            request.client.host if request.client else "unknown",
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide a valid 'X-API-Key' or 'Authorization: Bearer <key>' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return extracted_key
