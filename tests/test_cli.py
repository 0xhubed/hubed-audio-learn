"""CLI unit tests — exercise argparse + dispatch without real providers."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hubed_audio_learn import cli
from hubed_audio_learn.config import Config


def test_version_command_prints_version(capsys):
    rc = cli.main(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0.1.0" in out


def test_doctor_reports_config(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.chdir(tmp_path)
    with patch("hubed_audio_learn.cli.shutil.which", return_value="/usr/local/bin/claude"):
        rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "GEMINI_API_KEY: set" in out
    assert "claude binary:" in out


def test_doctor_flags_missing_gemini_key(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    with patch("hubed_audio_learn.cli.shutil.which", return_value=None):
        rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert rc != 0
    assert "GEMINI_API_KEY: MISSING" in out
    assert "claude binary: NOT FOUND" in out


def test_podcast_command_invokes_pipeline_stages(monkeypatch, tmp_path, load_fixture):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "out"

    fake_cfg = Config(
        gemini_api_key="x",
        output_dir=output_dir.resolve(),
        work_dir=(tmp_path / "work").resolve(),
    )

    with patch("hubed_audio_learn.cli.load_config", return_value=fake_cfg), \
         patch("hubed_audio_learn.cli.run_research") as research, \
         patch("hubed_audio_learn.cli.run_outline") as outline, \
         patch("hubed_audio_learn.cli.run_script") as script, \
         patch("hubed_audio_learn.cli.run_tts") as tts, \
         patch("hubed_audio_learn.cli.run_html_render") as html_render, \
         patch("hubed_audio_learn.cli.run_package") as package, \
         patch("hubed_audio_learn.cli.load_llm_provider"), \
         patch("hubed_audio_learn.cli.load_tts_provider"):

        # seed the work dir with fixtures so the patched stages don't need to write
        def _seed(*args, **kwargs):
            wd = kwargs.get("work_dir")
            (wd / "outline.json").write_text(json.dumps(load_fixture("sample_outline.json")))
            (wd / "script.json").write_text(json.dumps(load_fixture("sample_script.json")))
            (wd / "timing.json").write_text(json.dumps(load_fixture("sample_timing.json")))
            (wd / "episode.mp3").write_bytes(b"ID3")
            (wd / "episode.html").write_text("<html></html>")
            return wd / "stub.json"

        research.side_effect = _seed
        outline.side_effect = _seed
        script.side_effect = _seed
        tts.return_value = (Path("episode.mp3"), Path("timing.json"))
        html_render.return_value = Path("episode.html")
        package.return_value = output_dir / "manifest.json"

        rc = cli.main(["podcast", "Kalman filters", "--length", "medium"])

    assert rc == 0
    research.assert_called_once()
    outline.assert_called_once()
    script.assert_called_once()
    tts.assert_called_once()
    html_render.assert_called_once()
    package.assert_called_once()


def test_podcast_classifies_inputs_into_topic_and_docs(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.chdir(tmp_path)
    doc = tmp_path / "note.md"
    doc.write_text("hello")

    topic, docs = cli._classify_inputs(["Kalman", "filters", str(doc)])
    assert topic == "Kalman filters"
    assert docs == [doc]


def test_podcast_rejects_empty_topic(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.chdir(tmp_path)
    doc = tmp_path / "note.md"
    doc.write_text("hi")
    rc = cli.main(["podcast", str(doc)])
    assert rc != 0
    err = capsys.readouterr().err
    assert "topic" in err.lower()
