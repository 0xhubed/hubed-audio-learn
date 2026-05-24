"""LLM provider implementations."""
from hubed_audio_learn.providers.llm.base import LLMProvider
from hubed_audio_learn.providers.llm.claude import ClaudeProvider

__all__ = ["ClaudeProvider", "LLMProvider", "load_llm_provider"]


def load_llm_provider(name: str, *, claude_bin: str = "claude") -> LLMProvider:
    if name == "claude":
        return ClaudeProvider(binary=claude_bin)
    raise ValueError(f"Unknown LLM provider: {name!r}. Phase 1 supports only 'claude'.")
