"""Unit tests for live LLM providers and OpenAICompatibleProvider implementation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ai_services.providers.factory import get_llm_provider
from ai_services.providers.mock import DeterministicMockLLMProvider
from ai_services.providers.openai_compatible import OpenAICompatibleProvider
from pydantic import BaseModel
from shared.config import Settings


class MockOutputModel(BaseModel):
    summary: str
    confidence: float


def test_factory_returns_mock_when_configured():
    """Verify factory returns DeterministicMockLLMProvider when provider is 'mock'."""
    settings = Settings(llm_provider="mock", llm_api_key="sk-test-mock")
    provider = get_llm_provider(settings)
    assert isinstance(provider, DeterministicMockLLMProvider)


def test_factory_returns_mock_when_key_missing():
    """Verify factory gracefully falls back to mock provider if no API key is set."""
    settings = Settings(llm_provider="openai", llm_api_key=None)
    provider = get_llm_provider(settings)
    assert isinstance(provider, DeterministicMockLLMProvider)


def test_factory_returns_openai_when_configured():
    """Verify factory instantiates OpenAICompatibleProvider when provider is set with key."""
    settings = Settings(
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_api_key="sk-live-secret-test-key",
        llm_base_url="https://api.openai.com/v1",
        llm_timeout_seconds=25,
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "gpt-4o-mini"
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.timeout == 25
    # Verify API key is never exposed via string representation
    assert "sk-live-secret-test-key" not in str(provider)


def test_openai_provider_missing_key_raises_error():
    """Verify calling generate without an API key raises ValueError."""
    provider = OpenAICompatibleProvider(api_key=None)
    with pytest.raises(ValueError, match="LLM API key not configured"):
        provider.generate("Test prompt")


def test_openai_provider_generate_success():
    """Verify generate invokes chat completions with proper headers and body."""
    provider = OpenAICompatibleProvider(
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk-test-token",
        model="llama-3.3-70b-versatile",
        timeout=15,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Net recognized revenue is €408,602.64."}}]
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = provider.generate(prompt="What is revenue?", system_prompt="You are a financial AI.")
        assert res == "Net recognized revenue is €408,602.64."

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer gsk-test-token"
        assert call_kwargs["json"]["model"] == "llama-3.3-70b-versatile"
        assert len(call_kwargs["json"]["messages"]) == 2


def test_openai_provider_generate_structured():
    """Verify generate_structured parses JSON payload conforming to target model."""
    provider = OpenAICompatibleProvider(
        api_key="sk-test-token",
        model="gpt-4o-mini",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"summary": "Reconciled Accrual Revenue", "confidence": 0.99}\n```'
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        structured = provider.generate_structured(
            prompt="Analyze portfolio", response_model=MockOutputModel
        )
        assert isinstance(structured, MockOutputModel)
        assert structured.summary == "Reconciled Accrual Revenue"
        assert structured.confidence == 0.99


def test_openai_provider_repr_masks_secret():
    """Verify string representation of OpenAI provider masks the API key."""
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        api_key="sk-live-secret-key-1234567890",
        model="gpt-4o",
    )
    repr_str = repr(provider)
    assert "sk-live-secret-key-1234567890" not in repr_str
    assert "sk-...7890" in repr_str
    assert "gpt-4o" in repr_str
