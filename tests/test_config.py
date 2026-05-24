"""Config loading from environment with sensible defaults."""
from __future__ import annotations

from pathlib import Path

import pytest

from hubed_audio_learn.config import Config, load_config


def test_load_config_defaults(monkeypatch, tmp_path):
    for var in [
        "GEMINI_API_KEY", "LLM_PROVIDER", "TTS_PROVIDER", "OUTPUT_DIR", "WORK_DIR",
        "HOST_A_NAME", "HOST_A_VOICE", "HOST_B_NAME", "HOST_B_VOICE",
        "GEMINI_TTS_MODEL", "CLAUDE_BIN", "CLAUDE_TIMEOUT_SECONDS", "LOG_LEVEL",
    ]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)

    cfg = load_config()
    assert cfg.gemini_api_key == "test-key"
    assert cfg.llm_provider == "claude"
    assert cfg.tts_provider == "gemini"
    assert cfg.output_dir == Path("./output").resolve()
    assert cfg.host_a_name == "Alex"
    assert cfg.host_b_voice == "Leda"
    assert cfg.claude_timeout_seconds == 600


def test_load_config_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("HOST_A_NAME", "Robin")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("CLAUDE_TIMEOUT_SECONDS", "120")

    cfg = load_config()
    assert cfg.host_a_name == "Robin"
    assert cfg.output_dir == (tmp_path / "out").resolve()
    assert cfg.claude_timeout_seconds == 120


def test_config_is_immutable():
    cfg = Config(gemini_api_key="x")
    with pytest.raises(Exception):
        cfg.gemini_api_key = "y"  # type: ignore[misc]
