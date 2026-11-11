"""Abstract base class interface for Large Language Model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Abstract interface decoupling AI workflows from specific LLM vendors."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate unstructured text completion for the supplied prompt."""
        raise NotImplementedError

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Generate structured response conforming to the supplied Pydantic model."""
        raise NotImplementedError
