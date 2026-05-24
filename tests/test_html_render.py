"""HTML renderer unit tests."""
from __future__ import annotations

import json
import re
from pathlib import Path

from hubed_audio_learn.pipeline.html_render import run_html_render


def test_run_html_render_emits_self_contained_html(tmp_work_dir: Path, load_fixture):
    (tmp_work_dir / "outline.json").write_text(json.dumps(load_fixture("sample_outline.json")))
    (tmp_work_dir / "script.json").write_text(json.dumps(load_fixture("sample_script.json")))
    (tmp_work_dir / "timing.json").write_text(json.dumps(load_fixture("sample_timing.json")))

    out = run_html_render(work_dir=tmp_work_dir, mp3_filename="episode.mp3")

    assert out == tmp_work_dir / "episode.html"
    html = out.read_text(encoding="utf-8")

    # Audio element references the MP3
    assert 'src="episode.mp3"' in html
    # One slide per unique figure referenced by the script
    assert html.count('class="slide"') == 2
    # KaTeX LaTeX is embedded as data attribute
    assert "data-latex=" in html
    # Timing JSON is embedded
    timing_match = re.search(r'id="timing-data"[^>]*>([^<]+)<', html)
    assert timing_match is not None
    assert json.loads(timing_match.group(1))["turns"][1]["start_seconds"] == 3.5
    # Markers map turn-index -> figure_id
    markers_match = re.search(r'id="markers-data"[^>]*>([^<]+)<', html)
    assert markers_match is not None
    markers = json.loads(markers_match.group(1))
    assert markers["1"] == "fig-scenario-car"
    assert markers["2"] == "fig-predict"
