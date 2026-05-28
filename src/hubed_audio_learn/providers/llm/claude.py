"""Claude provider — wraps `claude --print` subprocess invocation."""
from __future__ import annotations

import re
import subprocess
from typing import Iterable

from hubed_audio_learn.providers.llm.base import LLMProvider

# `claude --print` frequently wraps JSON in a ```json ... ``` (or bare ``` ... ```)
# markdown fence even when prompted not to. Strip it so downstream json.loads succeeds.
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\n(.*)\n```$", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """Strip surrounding whitespace and a single markdown code fence, if present."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, binary: str = "claude"):
        self.binary = binary

    def generate(
        self,
        prompt: str,
        *,
        allowed_tools: Iterable[str] | None = None,
        timeout_seconds: int = 600,
    ) -> str:
        cmd: list[str] = [self.binary, "--print"]
        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Claude CLI not found at '{self.binary}'. Install it (https://docs.anthropic.com/claude/docs/claude-code) or set CLAUDE_BIN."
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"claude --print failed with exit code {result.returncode}: {result.stderr.strip()}"
            )
        return _strip_code_fences(result.stdout)
