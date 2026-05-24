"""Abstract TTS provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from hubed_audio_learn.schemas import Script, Timing


class TTSProvider(ABC):
    name: str
    supported_languages: list[str]

    @abstractmethod
    def render(self, script: Script) -> tuple[bytes, Timing]:
        """Render dialogue to MP3 bytes plus per-turn timing.

        Returns:
            (mp3_bytes, timing) — `mp3_bytes` is a complete MP3 file
            payload; `timing` lists per-turn start offsets in seconds.
        """
        raise NotImplementedError
