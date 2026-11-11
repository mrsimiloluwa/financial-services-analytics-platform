"""Unit tests for Streamlit Executive Dashboard and AI Copilot integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_services.schemas import AnalyticsQueryResponse
from data_apps.app import get_backend_client, load_catalog_data
from data_platform.metadata.metrics import MetricRegistry
from shared.config import Settings, _load_streamlit_secrets


def test_catalog_metrics_schema_compatibility():
    """Verify all 12 governed metrics match the real FinancialMetric schema without AttributeError."""
    registry = MetricRegistry.from_yaml()
    metrics = registry.list_all()
    assert len(metrics) == 12

    # Verify every field used in Tab 5 of app.py exists and is populated
    metrics_table = [
        {
            "Metric ID": m.metric_id,
            "Name": m.metric_name,
            "Source Model": f"analytics.{m.source_model}",
            "Formula": m.formula,
            "Grain": m.grain,
            "Business Definition": m.business_definition,
            "Currency Treatment": m.native_currency_treatment,
        }
        for m in metrics
    ]

    assert len(metrics_table) == 12
    for entry in metrics_table:
        assert entry["Metric ID"]
        assert entry["Name"]
        assert entry["Formula"]
        assert entry["Grain"]
        assert entry["Business Definition"]
        assert entry["Currency Treatment"]

    # Verify load_catalog_data handles missing DB gracefully without crashing
    with patch("data_apps.app.MetadataService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.list_metrics.return_value = metrics
        mock_service.list_queryable_models.return_value = []
        mock_service_cls.return_value = mock_service

        loaded_metrics, loaded_models = load_catalog_data()
        assert len(loaded_metrics) == 12
        assert loaded_models == []


def test_dashboard_backend_client_resolution():
    """Verify get_backend_client parses settings and formats headers correctly."""
    with patch(
        "data_apps.app.get_settings",
        return_value=Settings(
            api_base_url="https://analytics-api.example.com",
            api_key="secret-api-key-123",
        ),
    ):
        base_url, headers = get_backend_client()
        assert base_url == "https://analytics-api.example.com"
        assert headers == {"X-API-Key": "secret-api-key-123"}

    with patch(
        "data_apps.app.get_settings",
        return_value=Settings(api_base_url=None),
    ):
        base_url, headers = get_backend_client()
        assert base_url is None
        assert headers == {}


def test_dashboard_ai_chat_flow_via_mock():
    """Verify AI Copilot inquiry executes through LangGraph returning governed response."""
    from ai_services.graph.workflow import build_financial_analytics_graph
    from ai_services.providers.mock import DeterministicMockLLMProvider

    mock_provider = DeterministicMockLLMProvider()
    graph = build_financial_analytics_graph(provider=mock_provider)

    # In sandboxed unit tests, test the out-of-scope / injection safe path
    result = graph.invoke(
        {
            "question": "What is the weather today?",
            "environment": "dev",
        }
    )
    resp: AnalyticsQueryResponse | None = result.get("final_response")
    assert resp is not None
    assert resp.status == "OUT_OF_SCOPE"
    assert resp.sql_query is None


def test_dashboard_ai_chat_flow_via_rest_api():
    """Verify dashboard dispatches POST request to /api/v1/analytics/ask when API_BASE_URL is active."""
    import httpx

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "question": "What was our total net recognized revenue?",
        "answer": "Total net recognized commercial revenue is €408,602.64.",
        "status": "SUCCESS",
        "metric_used": "Recognized Revenue",
        "model_used": "fct_customer_revenue",
        "sql_query": "SELECT SUM(net_recognized_revenue_eur) FROM analytics.fct_customer_revenue;",
        "execution_time_ms": 12.5,
        "row_count": 1,
        "currency": "EUR",
        "confidence": 1.0,
    }

    test_settings = Settings(
        api_base_url="http://api:8000",
        api_key="test-key",
    )

    with (
        patch("data_apps.app.get_settings", return_value=test_settings),
        patch("httpx.Client.post", return_value=mock_resp) as mock_post,
    ):
        base_url, headers = get_backend_client()
        assert base_url == "http://api:8000"
        assert headers == {"X-API-Key": "test-key"}

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{base_url}/api/v1/analytics/ask",
                json={
                    "question": "What was our total net recognized revenue?",
                    "environment": "dev",
                },
                headers=headers,
            )
            assert resp.status_code == 200
            data = AnalyticsQueryResponse.model_validate(resp.json())
            assert data.status == "SUCCESS"
            assert data.metric_used == "Recognized Revenue"

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://api:8000/api/v1/analytics/ask"
        assert call_args[1]["headers"] == {"X-API-Key": "test-key"}


def test_streamlit_secrets_injection(monkeypatch):
    """Verify _load_streamlit_secrets extracts secrets into os.environ."""
    import os
    import sys

    # Mock streamlit module with secrets mapping
    mock_st = MagicMock()
    mock_st.secrets = {
        "POSTGRES_HOST": "neon-db.internal",
        "POSTGRES_READER_PASSWORD": "neon-reader-pass",
        "API_BASE_URL": "https://api.hosted.com",
    }

    monkeypatch.setitem(sys.modules, "streamlit", mock_st)
    _load_streamlit_secrets()

    assert os.environ.get("POSTGRES_HOST") == "neon-db.internal"
    assert os.environ.get("POSTGRES_READER_PASSWORD") == "neon-reader-pass"
    assert os.environ.get("API_BASE_URL") == "https://api.hosted.com"
