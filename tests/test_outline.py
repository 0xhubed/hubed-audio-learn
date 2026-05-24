"""Outline stage unit tests with the LLM provider mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hubed_audio_learn.pipeline.outline import run_outline
from hubed_audio_learn.schemas import Outline


def test_run_outline_writes_validated_outline(tmp_work_dir: Path, load_fixture):
    research = load_fixture("sample_research.json")
    outline = load_fixture("sample_outline.json")
    (tmp_work_dir / "research_bundle.json").write_text(json.dumps(research))

    llm = MagicMock()
    llm.generate.return_value = json.dumps(outline)

    out_path = run_outline(
        work_dir=tmp_work_dir,
        target_length="medium",
        user_prompt="Be intuitive then deep.",
        llm=llm,
    )
    assert out_path == tmp_work_dir / "outline.json"
    parsed = Outline.model_validate_json(out_path.read_text())
    assert parsed.target_length == "medium"
    assert llm.generate.call_args.kwargs.get("allowed_tools") in (None, [])


def test_run_outline_retries_once_on_invalid_json(tmp_work_dir: Path, load_fixture):
    research = load_fixture("sample_research.json")
    outline = load_fixture("sample_outline.json")
    (tmp_work_dir / "research_bundle.json").write_text(json.dumps(research))

    llm = MagicMock()
    llm.generate.side_effect = ["not json", json.dumps(outline)]
    run_outline(work_dir=tmp_work_dir, target_length="medium", user_prompt=None, llm=llm)
    assert llm.generate.call_count == 2


def test_run_outline_raises_after_two_failures(tmp_work_dir: Path, load_fixture):
    research = load_fixture("sample_research.json")
    (tmp_work_dir / "research_bundle.json").write_text(json.dumps(research))
    llm = MagicMock()
    llm.generate.return_value = "still bad"
    with pytest.raises(RuntimeError, match="outline"):
        run_outline(work_dir=tmp_work_dir, target_length="medium", user_prompt=None, llm=llm)
