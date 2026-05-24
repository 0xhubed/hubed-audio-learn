"""Stage 1 — research a topic and emit research_bundle.json."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from hubed_audio_learn.providers.llm.base import LLMProvider
from hubed_audio_learn.schemas import ResearchBundle

_ALLOWED_TOOLS = ["WebFetch", "WebSearch", "Read"]


def _load_system_prompt() -> str:
    return resources.files("hubed_audio_learn.prompts").joinpath("research_system.txt").read_text(encoding="utf-8")


def _extract_doc_text(path: Path) -> tuple[str, str]:
    """Returns (kind, extracted_text)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader  # local import — only when needed
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return "pdf", text
    if suffix == ".md":
        return "markdown", path.read_text(encoding="utf-8")
    if suffix == ".rst":
        return "rst", path.read_text(encoding="utf-8")
    return "text", path.read_text(encoding="utf-8")


def _build_prompt(
    topic: str,
    user_prompt: str | None,
    user_docs: list[dict],
    retry_error: str | None = None,
) -> str:
    system = _load_system_prompt()
    parts = [
        system,
        "",
        f"Topic: {topic}",
    ]
    if user_prompt:
        parts.append(f"User prompt: {user_prompt}")
    if user_docs:
        parts.append("")
        parts.append("User-supplied documents (already extracted):")
        for d in user_docs:
            parts.append(f"--- {d['path']} ({d['kind']}) ---")
            parts.append(d["extracted_text"])
    if retry_error:
        parts.append("")
        parts.append("Your previous response did not parse as valid JSON for the schema:")
        parts.append(retry_error)
        parts.append("Return ONLY the corrected JSON object.")
    return "\n".join(parts)


def run_research(
    *,
    topic: str,
    user_prompt: str | None,
    user_doc_paths: list[Path],
    work_dir: Path,
    llm: LLMProvider,
    timeout_seconds: int = 600,
) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path = work_dir / "research_bundle.json"

    user_docs = []
    for p in user_doc_paths:
        kind, text = _extract_doc_text(p)
        user_docs.append({"path": str(p), "kind": kind, "extracted_text": text})

    last_error: str | None = None
    for attempt in range(2):
        prompt = _build_prompt(topic, user_prompt, user_docs, retry_error=last_error if attempt == 1 else None)
        raw = llm.generate(prompt, allowed_tools=_ALLOWED_TOOLS, timeout_seconds=timeout_seconds)
        try:
            data = json.loads(raw)
            bundle = ResearchBundle.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            continue
        # If the model returned an empty user_docs, inject the ones we extracted locally
        if user_docs and not bundle.user_docs:
            data["user_docs"] = user_docs
            bundle = ResearchBundle.model_validate(data)
        out_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        return out_path

    raise RuntimeError(f"research stage failed after 2 attempts: {last_error}")
