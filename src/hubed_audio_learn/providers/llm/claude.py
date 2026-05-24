"""Claude provider — wraps `claude --print` subprocess invocation."""
from __future__ import annotations

import subprocess
from typing import Iterable

from hubed_audio_learn.providers.llm.base import LLMProvider


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
        return result.stdout.strip()
