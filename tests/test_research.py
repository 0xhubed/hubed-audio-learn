"""Research stage unit tests with the LLM provider mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hubed_audio_learn.pipeline.research import run_research
from hubed_audio_learn.schemas import ResearchBundle


def test_run_research_writes_validated_bundle(tmp_work_dir: Path, load_fixture):
    sample = load_fixture("sample_research.json")
    llm = MagicMock()
    llm.generate.return_value = json.dumps(sample)

    out_path = run_research(
        topic="Kalman filters",
        user_prompt="Explain intuitively, then go deep into the math.",
        user_doc_paths=[],
        work_dir=tmp_work_dir,
        llm=llm,
    )

    assert out_path == tmp_work_dir / "research_bundle.json"
    parsed = ResearchBundle.model_validate_json(out_path.read_text())
    assert parsed.topic == "Kalman filters"
    llm.generate.assert_called_once()
    call = llm.generate.call_args
    assert "WebFetch" in (call.kwargs.get("allowed_tools") or [])
    assert "WebSearch" in (call.kwargs.get("allowed_tools") or [])


def test_run_research_retries_once_on_invalid_json(tmp_work_dir: Path, load_fixture):
    sample = load_fixture("sample_research.json")
    llm = MagicMock()
    llm.generate.side_effect = ["this is not json", json.dumps(sample)]

    run_research(
        topic="Kalman filters",
        user_prompt=None,
        user_doc_paths=[],
        work_dir=tmp_work_dir,
        llm=llm,
    )
    assert llm.generate.call_count == 2
    # Second invocation receives the validation error in the prompt
    second_prompt = llm.generate.call_args_list[1].args[0]
    assert "previous response" in second_prompt.lower() or "invalid" in second_prompt.lower()


def test_run_research_raises_after_two_failures(tmp_work_dir: Path):
    llm = MagicMock()
    llm.generate.return_value = "still not json"
    with pytest.raises(RuntimeError, match="research"):
        run_research(
            topic="x",
            user_prompt=None,
            user_doc_paths=[],
            work_dir=tmp_work_dir,
            llm=llm,
        )
    assert llm.generate.call_count == 2


def test_run_research_includes_pdf_text_in_prompt(tmp_work_dir: Path, load_fixture, tmp_path):
    sample = load_fixture("sample_research.json")
    pdf_path = tmp_path / "note.txt"
    pdf_path.write_text("KALMAN ROCKS")

    llm = MagicMock()
    llm.generate.return_value = json.dumps(sample)

    run_research(
        topic="Kalman filters",
        user_prompt=None,
        user_doc_paths=[pdf_path],
        work_dir=tmp_work_dir,
        llm=llm,
    )
    prompt = llm.generate.call_args.args[0]
    assert "KALMAN ROCKS" in prompt
