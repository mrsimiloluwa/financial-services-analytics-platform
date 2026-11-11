"""Factory for instantiating configured LLM provider."""

from __future__ import annotations

import logging

from ai_services.providers.base import BaseLLMProvider
from ai_services.providers.mock import DeterministicMockLLMProvider
from ai_services.providers.openai_compatible import OpenAICompatibleProvider
from shared.config import Settings, get_settings

logger = logging.getLogger(__name__)


def get_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    """Return configured LLM provider instance based on application settings."""
    cfg = settings or get_settings()

    if cfg.llm_provider.lower() == "mock" or not cfg.llm_api_key:
        logger.info("Using DeterministicMockLLMProvider for AI analytics")
        return DeterministicMockLLMProvider()

    logger.info("Using OpenAICompatibleProvider (%s) for AI analytics", cfg.llm_model)
    return OpenAICompatibleProvider.from_settings(cfg)
