"""Environment configuration for the pipeline."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


class Config(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    gemini_api_key: str = ""
    llm_provider: str = "claude"
    tts_provider: str = "gemini"
    output_dir: Path = Field(default_factory=lambda: Path("./output").resolve())
    work_dir: Path = Field(default_factory=lambda: Path("./.work").resolve())

    host_a_name: str = "Alex"
    host_a_voice: str = "Charon"
    host_b_name: str = "Sam"
    host_b_voice: str = "Leda"

    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"

    claude_bin: str = "claude"
    claude_timeout_seconds: int = 600

    log_level: str = "INFO"


def load_config(env_file: str | Path | None = ".env") -> Config:
    """Load env vars (optionally from .env) and return a frozen Config."""
    if env_file and Path(env_file).exists():
        load_dotenv(env_file, override=False)

    def _path(key: str, default: str) -> Path:
        return Path(os.environ.get(key, default)).resolve()

    return Config(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        llm_provider=os.environ.get("LLM_PROVIDER", "claude"),
        tts_provider=os.environ.get("TTS_PROVIDER", "gemini"),
        output_dir=_path("OUTPUT_DIR", "./output"),
        work_dir=_path("WORK_DIR", "./.work"),
        host_a_name=os.environ.get("HOST_A_NAME", "Alex"),
        host_a_voice=os.environ.get("HOST_A_VOICE", "Charon"),
        host_b_name=os.environ.get("HOST_B_NAME", "Sam"),
        host_b_voice=os.environ.get("HOST_B_VOICE", "Leda"),
        gemini_tts_model=os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        claude_bin=os.environ.get("CLAUDE_BIN", "claude"),
        claude_timeout_seconds=int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "600")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
