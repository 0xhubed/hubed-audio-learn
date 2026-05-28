"""Package stage unit tests."""
from __future__ import annotations

import json
from pathlib import Path

from hubed_audio_learn.pipeline.package import run_package


def _seed_work_dir(work: Path, load_fixture) -> None:
    (work / "outline.json").write_text(json.dumps(load_fixture("sample_outline.json")))
    (work / "script.json").write_text(json.dumps(load_fixture("sample_script.json")))
    (work / "timing.json").write_text(json.dumps(load_fixture("sample_timing.json")))
    (work / "episode.mp3").write_bytes(b"ID3\x00MP3")
    (work / "episode.html").write_text("<html>player</html>")


def test_run_package_moves_artifacts_with_dated_names(tmp_work_dir: Path, tmp_output_dir: Path, load_fixture):
    _seed_work_dir(tmp_work_dir, load_fixture)
    manifest = run_package(
        work_dir=tmp_work_dir,
        output_dir=tmp_output_dir,
        topic="Kalman filters",
        date_str="2026-05-23",
        providers={"llm": "claude", "tts": "gemini"},
        stage_durations={"research": 12.3, "outline": 5.1, "script": 6.0, "tts": 30.0, "html_render": 0.4},
    )

    files = sorted(p.name for p in tmp_output_dir.iterdir())
    assert "2026-05-23-kalman-filters.mp3" in files
    assert "2026-05-23-kalman-filters.html" in files
    assert "2026-05-23-kalman-filters.transcript.md" in files
    assert "2026-05-23-kalman-filters.outline.json" in files
    assert "2026-05-23-kalman-filters.manifest.json" in files

    transcript = (tmp_output_dir / "2026-05-23-kalman-filters.transcript.md").read_text()
    assert "[00:00] Alex:" in transcript
    assert "[00:03] Sam:" in transcript  # 3.5s rounds to 00:03
    assert "[00:08] Alex:" in transcript

    manifest_data = json.loads((tmp_output_dir / "2026-05-23-kalman-filters.manifest.json").read_text())
    assert manifest_data["providers"] == {"llm": "claude", "tts": "gemini"}
    assert manifest_data["topic"] == "Kalman filters"
    assert manifest_data["stage_durations_seconds"]["tts"] == 30.0
    assert "fig-scenario-car" in [f["id"] for f in manifest_data["figures_referenced"]]
    assert manifest is not None


def test_run_package_does_not_clobber_existing_episode(tmp_work_dir: Path, tmp_output_dir: Path, load_fixture):
    _seed_work_dir(tmp_work_dir, load_fixture)
    common = dict(
        work_dir=tmp_work_dir,
        output_dir=tmp_output_dir,
        topic="Kalman filters",
        date_str="2026-05-23",
        providers={"llm": "claude", "tts": "gemini"},
        stage_durations={},
    )
    run_package(**common)
    run_package(**common)  # same day, same topic — must not overwrite the first

    names = sorted(p.name for p in tmp_output_dir.iterdir())
    assert "2026-05-23-kalman-filters.mp3" in names
    assert "2026-05-23-kalman-filters-2.mp3" in names


def test_run_package_html_audio_src_points_to_renamed_mp3(tmp_work_dir: Path, tmp_output_dir: Path, load_fixture):
    _seed_work_dir(tmp_work_dir, load_fixture)
    # html_render wrote src="episode.mp3" — packaging should rewrite to the final name
    (tmp_work_dir / "episode.html").write_text('<audio src="episode.mp3"></audio>')

    run_package(
        work_dir=tmp_work_dir,
        output_dir=tmp_output_dir,
        topic="Kalman filters",
        date_str="2026-05-23",
        providers={"llm": "claude", "tts": "gemini"},
        stage_durations={},
    )
    final_html = (tmp_output_dir / "2026-05-23-kalman-filters.html").read_text()
    assert 'src="2026-05-23-kalman-filters.mp3"' in final_html
    assert 'src="episode.mp3"' not in final_html
