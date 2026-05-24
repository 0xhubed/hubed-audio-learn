"""Stage 3 — convert outline.json into script.json via one LLM call."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from hubed_audio_learn.providers.llm.base import LLMProvider
from hubed_audio_learn.schemas import Script


def _load_system_prompt() -> str:
    return resources.files("hubed_audio_learn.prompts").joinpath("script_system.txt").read_text(encoding="utf-8")


def _build_prompt(
    outline_json: str,
    target_length: str,
    host_a_name: str,
    host_a_voice: str,
    host_b_name: str,
    host_b_voice: str,
    retry_error: str | None = None,
) -> str:
    parts = [
        _load_system_prompt(),
        "",
        f"target_length: {target_length}",
        f"host_a: name={host_a_name}, voice_id={host_a_voice}",
        f"host_b: name={host_b_name}, voice_id={host_b_voice}",
        "",
        "Outline:",
        outline_json,
    ]
    if retry_error:
        parts.extend(["", "Your previous response did not validate:", retry_error, "Return ONLY the corrected JSON."])
    return "\n".join(parts)


def run_script(
    *,
    work_dir: Path,
    target_length: str,
    host_a_name: str,
    host_a_voice: str,
    host_b_name: str,
    host_b_voice: str,
    llm: LLMProvider,
    timeout_seconds: int = 600,
) -> Path:
    outline_path = work_dir / "outline.json"
    if not outline_path.exists():
        raise FileNotFoundError(f"outline.json not found in {work_dir}")
    outline_json = outline_path.read_text(encoding="utf-8")
    out_path = work_dir / "script.json"

    last_error: str | None = None
    for attempt in range(2):
        prompt = _build_prompt(
            outline_json,
            target_length,
            host_a_name,
            host_a_voice,
            host_b_name,
            host_b_voice,
            retry_error=last_error if attempt == 1 else None,
        )
        raw = llm.generate(prompt, allowed_tools=None, timeout_seconds=timeout_seconds)
        try:
            data = json.loads(raw)
            script = Script.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            continue
        out_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        return out_path

    raise RuntimeError(f"script stage failed after 2 attempts: {last_error}")
