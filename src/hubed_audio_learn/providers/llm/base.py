"""Abstract LLM provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        allowed_tools: Iterable[str] | None = None,
        timeout_seconds: int = 600,
    ) -> str:
        """Generate text from prompt. Returns the model's reply as a string."""
        raise NotImplementedError
