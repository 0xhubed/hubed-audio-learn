"""TTS provider implementations."""
from hubed_audio_learn.providers.tts.base import TTSProvider

__all__ = ["TTSProvider", "load_tts_provider"]


def load_tts_provider(name: str, *, api_key: str, model: str) -> TTSProvider:
    if name == "gemini":
        from hubed_audio_learn.providers.tts.gemini import GeminiTTSProvider
        return GeminiTTSProvider(api_key=api_key, model=model)
    raise ValueError(f"Unknown TTS provider: {name!r}. Phase 1 supports only 'gemini'.")
