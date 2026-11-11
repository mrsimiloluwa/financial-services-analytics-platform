"""Unit tests for API security, authentication, rate limiting, and telemetry."""

from __future__ import annotations

import pytest
from ai_services.api.app import app
from ai_services.api.security import RateLimiter
from fastapi.testclient import TestClient
from shared.config import Settings, get_settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_security_headers_present(client: TestClient):
    """Verify security headers are injected into HTTP responses."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in resp.headers


def test_auth_disabled_allows_anonymous_access(client: TestClient):
    """When API_AUTH_ENABLED=False, endpoints allow anonymous development access."""
    app.dependency_overrides[get_settings] = lambda: Settings(api_auth_enabled=False)
    try:
        resp = client.get("/api/v1/analytics/overview?environment=test")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_auth_enabled_rejects_missing_key(client: TestClient):
    """When API_AUTH_ENABLED=True, requests without API key return 401 Unauthorized."""
    secure_settings = Settings(api_auth_enabled=True, api_key="test-secret-key-12345")
    app.dependency_overrides[get_settings] = lambda: secure_settings
    try:
        resp = client.get("/api/v1/analytics/overview?environment=test")
        assert resp.status_code == 401
        assert "Invalid or missing API key" in resp.json()["detail"]

        # Also check catalog endpoints require auth
        resp_metrics = client.get("/api/v1/analytics/metrics")
        assert resp_metrics.status_code == 401
        resp_models = client.get("/api/v1/analytics/models")
        assert resp_models.status_code == 401
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_auth_enabled_accepts_valid_api_key_header(client: TestClient):
    """When API_AUTH_ENABLED=True, valid X-API-Key header is accepted."""
    secure_settings = Settings(api_auth_enabled=True, api_key="test-secret-key-12345")
    app.dependency_overrides[get_settings] = lambda: secure_settings
    try:
        headers = {"X-API-Key": "test-secret-key-12345"}
        resp = client.get("/api/v1/analytics/overview?environment=test", headers=headers)
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_auth_enabled_accepts_valid_bearer_token(client: TestClient):
    """When API_AUTH_ENABLED=True, valid Bearer token is accepted."""
    secure_settings = Settings(api_auth_enabled=True, api_key="test-secret-key-12345")
    app.dependency_overrides[get_settings] = lambda: secure_settings
    try:
        headers = {"Authorization": "Bearer test-secret-key-12345"}
        resp = client.get("/api/v1/analytics/overview?environment=test", headers=headers)
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_public_endpoints_exempt_from_auth(client: TestClient):
    """Verify health and metadata endpoints remain accessible even with auth enabled."""
    secure_settings = Settings(api_auth_enabled=True, api_key="test-secret-key-12345")
    app.dependency_overrides[get_settings] = lambda: secure_settings
    try:
        resp_root = client.get("/")
        assert resp_root.status_code == 200

        resp_health = client.get("/health")
        assert resp_health.status_code == 200

        resp_telemetry = client.get("/telemetry")
        assert resp_telemetry.status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_rate_limiter_throttles_excess_requests():
    """Verify RateLimiter triggers rejection when limit is exceeded."""
    limiter = RateLimiter(requests_per_minute=3)
    client_ip = "192.168.1.100"

    assert limiter.check(client_ip) is True
    assert limiter.check(client_ip) is True
    assert limiter.check(client_ip) is True
    # 4th request in the same window exceeds limit
    assert limiter.check(client_ip) is False


def test_telemetry_endpoint_reports_activity(client: TestClient):
    """Verify telemetry endpoint returns live operational metrics."""
    resp = client.get("/telemetry")
    assert resp.status_code == 200
    data = resp.json()

    assert "uptime_seconds" in data
    assert "total_requests" in data
    assert data["total_requests"] >= 1
    assert "average_latency_ms" in data
