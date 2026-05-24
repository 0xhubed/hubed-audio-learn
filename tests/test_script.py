"""Script stage unit tests with the LLM provider mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hubed_audio_learn.pipeline.script import run_script
from hubed_audio_learn.schemas import Script


def test_run_script_writes_validated_script(tmp_work_dir: Path, load_fixture):
    outline = load_fixture("sample_outline.json")
    script = load_fixture("sample_script.json")
    (tmp_work_dir / "outline.json").write_text(json.dumps(outline))

    llm = MagicMock()
    llm.generate.return_value = json.dumps(script)

    out_path = run_script(
        work_dir=tmp_work_dir,
        target_length="medium",
        host_a_name="Alex",
        host_a_voice="gemini:Charon",
        host_b_name="Sam",
        host_b_voice="gemini:Leda",
        llm=llm,
    )
    assert out_path == tmp_work_dir / "script.json"
    parsed = Script.model_validate_json(out_path.read_text())
    assert len(parsed.turns) == 3
    prompt = llm.generate.call_args.args[0]
    assert "Alex" in prompt
    assert "gemini:Charon" in prompt


def test_run_script_retries_once_on_invalid_json(tmp_work_dir: Path, load_fixture):
    outline = load_fixture("sample_outline.json")
    script = load_fixture("sample_script.json")
    (tmp_work_dir / "outline.json").write_text(json.dumps(outline))
    llm = MagicMock()
    llm.generate.side_effect = ["nope", json.dumps(script)]
    run_script(
        work_dir=tmp_work_dir,
        target_length="medium",
        host_a_name="Alex",
        host_a_voice="gemini:Charon",
        host_b_name="Sam",
        host_b_voice="gemini:Leda",
        llm=llm,
    )
    assert llm.generate.call_count == 2


def test_run_script_raises_after_two_failures(tmp_work_dir: Path, load_fixture):
    outline = load_fixture("sample_outline.json")
    (tmp_work_dir / "outline.json").write_text(json.dumps(outline))
    llm = MagicMock()
    llm.generate.return_value = "junk"
    with pytest.raises(RuntimeError, match="script"):
        run_script(
            work_dir=tmp_work_dir,
            target_length="medium",
            host_a_name="Alex",
            host_a_voice="gemini:Charon",
            host_b_name="Sam",
            host_b_voice="gemini:Leda",
            llm=llm,
        )
