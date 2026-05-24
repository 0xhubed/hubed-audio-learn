"""Stage 4 — render script.json to episode.mp3 + timing.json via a TTS provider."""
from __future__ import annotations

from pathlib import Path

from hubed_audio_learn.providers.tts.base import TTSProvider
from hubed_audio_learn.schemas import Script


def run_tts(*, work_dir: Path, tts: TTSProvider) -> tuple[Path, Path]:
    script_path = work_dir / "script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"script.json not found in {work_dir}")
    script = Script.model_validate_json(script_path.read_text(encoding="utf-8"))

    mp3_bytes, timing = tts.render(script)

    mp3_path = work_dir / "episode.mp3"
    timing_path = work_dir / "timing.json"
    mp3_path.write_bytes(mp3_bytes)
    timing_path.write_text(timing.model_dump_json(indent=2), encoding="utf-8")
    return mp3_path, timing_path
