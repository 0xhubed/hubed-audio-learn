"""Stage 5 — render an interactive HTML player wrapping the MP3 and slides."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from hubed_audio_learn.schemas import Outline, Script, Timing


def _template_env() -> Environment:
    template_dir = resources.files("hubed_audio_learn.templates.html")
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _figure_first_starts(script: Script, timing: Timing) -> dict[str, float]:
    """First appearance time for each figure_id, in seconds."""
    start_by_index = {t.index: t.start_seconds for t in timing.turns}
    firsts: dict[str, float] = {}
    for i, turn in enumerate(script.turns):
        if turn.slide_marker and turn.slide_marker.figure_id not in firsts:
            firsts[turn.slide_marker.figure_id] = start_by_index.get(i, 0.0)
    return firsts


def _markers_map(script: Script) -> dict[str, str]:
    """Turn-index (as string for JSON object) -> figure_id of the active slide.

    A turn without an explicit slide_marker inherits the previous turn's marker.
    """
    result: dict[str, str] = {}
    current: str | None = None
    for i, turn in enumerate(script.turns):
        if turn.slide_marker:
            current = turn.slide_marker.figure_id
        if current is not None:
            result[str(i)] = current
    return result


def _ordered_figures(outline: Outline, script: Script, firsts: dict[str, float]) -> list[dict]:
    """All figures referenced by the script, in order of first appearance."""
    fig_lookup = {f.id: f for section in outline.sections for f in section.figures}
    seen: list[str] = []
    for turn in script.turns:
        if turn.slide_marker and turn.slide_marker.figure_id not in seen:
            seen.append(turn.slide_marker.figure_id)
    result = []
    for fig_id in seen:
        fig = fig_lookup.get(fig_id)
        if not fig:
            continue
        result.append({
            "id": fig.id,
            "kind": fig.kind,
            "caption": fig.caption,
            "latex": fig.latex,
            "body": fig.body,
            "first_start_seconds": round(firsts.get(fig.id, 0.0), 3),
        })
    return result


def run_html_render(*, work_dir: Path, mp3_filename: str) -> Path:
    outline = Outline.model_validate_json((work_dir / "outline.json").read_text(encoding="utf-8"))
    script = Script.model_validate_json((work_dir / "script.json").read_text(encoding="utf-8"))
    timing = Timing.model_validate_json((work_dir / "timing.json").read_text(encoding="utf-8"))

    firsts = _figure_first_starts(script, timing)
    figures = _ordered_figures(outline, script, firsts)
    markers = _markers_map(script)

    env = _template_env()
    template = env.get_template("player.html.j2")
    html = template.render(
        topic=outline.topic,
        mp3_filename=mp3_filename,
        figures=figures,
        timing_json=timing.model_dump_json(),
        markers_json=json.dumps(markers),
    )
    out_path = work_dir / "episode.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
