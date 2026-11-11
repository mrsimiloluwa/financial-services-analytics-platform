"""Production OpenAI-compatible API provider for live LLM inference."""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

import httpx
from ai_services.providers.base import BaseLLMProvider
from pydantic import BaseModel
from shared.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Invokes standard OpenAI-compatible chat completion APIs with timeout and error handling."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: int = 30,
    ) -> None:
        """Initialize provider with endpoint configuration."""
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> OpenAICompatibleProvider:
        """Factory from application Settings."""
        cfg = settings or get_settings()
        return cls(
            base_url=cfg.llm_base_url,
            api_key=cfg.llm_api_key,
            model=cfg.llm_model,
            timeout=cfg.llm_timeout_seconds,
        )

    def __repr__(self) -> str:
        """Safe string representation masking the API key secret."""
        masked_key = (
            f"{self.api_key[:3]}...{self.api_key[-4:]}"
            if self.api_key and len(self.api_key) > 7
            else ("***" if self.api_key else "None")
        )
        return (
            f"<OpenAICompatibleProvider model='{self.model}' "
            f"base_url='{self.base_url}' api_key='{masked_key}'>"
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute chat completion request."""
        if not self.api_key:
            raise ValueError("LLM API key not configured. Set LLM_API_KEY environment variable.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0),
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute structured JSON completion conforming to target Pydantic schema."""
        schema_json = json.dumps(response_model.model_json_schema())
        augmented_system = (
            f"{system_prompt or ''}\n\n"
            f"You MUST respond ONLY with valid JSON conforming to this JSON Schema:\n{schema_json}"
        )
        raw_text = self.generate(prompt=prompt, system_prompt=augmented_system, **kwargs)
        # Clean potential markdown fences
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return response_model.model_validate_json(cleaned.strip())
