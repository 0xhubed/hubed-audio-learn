"""Validate that every fixture roundtrips through its schema."""
from __future__ import annotations

import pytest

from hubed_audio_learn.schemas import Outline, ResearchBundle, Script, Timing


def test_research_bundle_roundtrips(load_fixture):
    data = load_fixture("sample_research.json")
    parsed = ResearchBundle.model_validate(data)
    assert parsed.model_dump(mode="json") == data


def test_outline_roundtrips(load_fixture):
    data = load_fixture("sample_outline.json")
    parsed = Outline.model_validate(data)
    assert parsed.topic == "Kalman filters"
    assert len(parsed.sections) == 2
    assert parsed.sections[1].figures[0].latex.startswith("\\hat{x}")


def test_script_roundtrips(load_fixture):
    data = load_fixture("sample_script.json")
    parsed = Script.model_validate(data)
    assert len(parsed.turns) == 3
    assert parsed.turns[1].slide_marker.figure_id == "fig-scenario-car"


def test_timing_roundtrips(load_fixture):
    data = load_fixture("sample_timing.json")
    parsed = Timing.model_validate(data)
    assert parsed.turns[2].start_seconds == 8.2


def test_outline_rejects_unknown_fields():
    bad = {
        "topic": "x",
        "target_length": "medium",
        "audience_assumed": "y",
        "sections": [],
        "extra_field": "boom",
    }
    with pytest.raises(Exception):
        Outline.model_validate(bad)


def test_script_rejects_invalid_speaker():
    bad = {
        "outline_ref": "outline.json",
        "host_a": {"name": "A", "voice_id": "v", "persona": "p"},
        "host_b": {"name": "B", "voice_id": "v", "persona": "p"},
        "turns": [{"speaker": "C", "text": "hi", "section_ref": "intro"}],
    }
    with pytest.raises(Exception):
        Script.model_validate(bad)
