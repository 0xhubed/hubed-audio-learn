"""Unit tests for the Claude subprocess wrapper using a mocked subprocess.run."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from hubed_audio_learn.providers.llm.claude import ClaudeProvider


class _FakeCompleted:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_generate_passes_prompt_via_stdin_and_returns_stdout():
    provider = ClaudeProvider(binary="claude")
    fake = _FakeCompleted(stdout="hello world\n")
    with patch("hubed_audio_learn.providers.llm.claude.subprocess.run", return_value=fake) as run:
        out = provider.generate("Say hi.", timeout_seconds=42)
    assert out == "hello world"
    cmd = run.call_args.args[0]
    assert cmd[0] == "claude"
    assert "--print" in cmd
    # No allowed tools => no --allowedTools flag
    assert "--allowedTools" not in cmd
    assert run.call_args.kwargs["input"] == "Say hi."
    assert run.call_args.kwargs["timeout"] == 42


def test_generate_with_allowed_tools_adds_flag():
    provider = ClaudeProvider(binary="claude")
    fake = _FakeCompleted(stdout="ok\n")
    with patch("hubed_audio_learn.providers.llm.claude.subprocess.run", return_value=fake) as run:
        provider.generate("topic", allowed_tools=["WebFetch", "WebSearch", "Read"])
    cmd = run.call_args.args[0]
    idx = cmd.index("--allowedTools")
    assert cmd[idx + 1] == "WebFetch,WebSearch,Read"


def test_generate_raises_on_nonzero_exit():
    provider = ClaudeProvider(binary="claude")
    fake = _FakeCompleted(stdout="", stderr="boom", returncode=2)
    with patch("hubed_audio_learn.providers.llm.claude.subprocess.run", return_value=fake):
        with pytest.raises(RuntimeError, match="exit code 2"):
            provider.generate("x")


def test_generate_raises_on_missing_binary():
    provider = ClaudeProvider(binary="claude-not-real")
    with patch(
        "hubed_audio_learn.providers.llm.claude.subprocess.run",
        side_effect=FileNotFoundError("not found"),
    ):
        with pytest.raises(RuntimeError, match="claude-not-real"):
            provider.generate("x")
