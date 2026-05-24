"""Stage 2 — convert research_bundle.json into outline.json via one LLM call."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from hubed_audio_learn.providers.llm.base import LLMProvider
from hubed_audio_learn.schemas import Outline


def _load_system_prompt() -> str:
    return resources.files("hubed_audio_learn.prompts").joinpath("outline_system.txt").read_text(encoding="utf-8")


def _build_prompt(
    research_bundle_json: str,
    target_length: str,
    user_prompt: str | None,
    retry_error: str | None = None,
) -> str:
    parts = [
        _load_system_prompt(),
        "",
        f"target_length: {target_length}",
    ]
    if user_prompt:
        parts.append(f"User prompt: {user_prompt}")
    parts.extend(["", "Research bundle:", research_bundle_json])
    if retry_error:
        parts.extend(["", "Your previous response did not validate:", retry_error, "Return ONLY the corrected JSON."])
    return "\n".join(parts)


def run_outline(
    *,
    work_dir: Path,
    target_length: str,
    user_prompt: str | None,
    llm: LLMProvider,
    timeout_seconds: int = 600,
) -> Path:
    research_path = work_dir / "research_bundle.json"
    if not research_path.exists():
        raise FileNotFoundError(f"research_bundle.json not found in {work_dir}")
    research_json = research_path.read_text(encoding="utf-8")
    out_path = work_dir / "outline.json"

    last_error: str | None = None
    for attempt in range(2):
        prompt = _build_prompt(
            research_json,
            target_length,
            user_prompt,
            retry_error=last_error if attempt == 1 else None,
        )
        raw = llm.generate(prompt, allowed_tools=None, timeout_seconds=timeout_seconds)
        try:
            data = json.loads(raw)
            outline = Outline.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            continue
        out_path.write_text(outline.model_dump_json(indent=2), encoding="utf-8")
        return out_path

    raise RuntimeError(f"outline stage failed after 2 attempts: {last_error}")
