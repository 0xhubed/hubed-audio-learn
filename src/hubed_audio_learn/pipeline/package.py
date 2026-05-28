"""Stage 6 — move finished artifacts into OUTPUT_DIR and write the manifest."""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from slugify import slugify

from hubed_audio_learn.schemas import Outline, Script, Timing


def _free_base(output_dir: Path, base: str) -> str:
    """Return `base`, or `base-2`, `base-3`, … — the first that has no `.mp3` yet.

    Filenames are deterministic (`<date>-<slug>`), so a same-day same-topic re-run
    would otherwise clobber a prior good episode. Since OUTPUT_DIR is typically a
    Syncthing/Obsidian-synced folder, that delete would propagate to the phone.
    """
    if not (output_dir / f"{base}.mp3").exists():
        return base
    n = 2
    while (output_dir / f"{base}-{n}.mp3").exists():
        n += 1
    return f"{base}-{n}"


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def _build_transcript(script: Script, timing: Timing) -> str:
    start_by_index = {t.index: t.start_seconds for t in timing.turns}
    lines: list[str] = []
    for i, turn in enumerate(script.turns):
        ts = _format_timestamp(start_by_index.get(i, 0.0))
        name = script.host_a.name if turn.speaker == "A" else script.host_b.name
        lines.append(f"[{ts}] {name}:")
        lines.append(turn.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_manifest(
    *,
    topic: str,
    date_str: str,
    slug: str,
    providers: dict[str, str],
    stage_durations: dict[str, float],
    outline: Outline,
    script: Script,
    timing: Timing,
    mp3_bytes_size: int,
) -> dict[str, Any]:
    figures_referenced = []
    seen: set[str] = set()
    for turn in script.turns:
        if turn.slide_marker and turn.slide_marker.figure_id not in seen:
            seen.add(turn.slide_marker.figure_id)
            figures_referenced.append({"id": turn.slide_marker.figure_id})

    return {
        "schema_version": 1,
        "topic": topic,
        "slug": slug,
        "date": date_str,
        "providers": providers,
        "stage_durations_seconds": stage_durations,
        "turn_count": len(script.turns),
        "tts_character_count": sum(len(t.text) for t in script.turns),
        "audio_duration_estimate_seconds": (
            timing.turns[-1].start_seconds if timing.turns else 0.0
        ),
        "mp3_bytes": mp3_bytes_size,
        "sources": [s.model_dump() for s in outline.sources_used],
        "figures_referenced": figures_referenced,
        "target_length": outline.target_length,
    }


def run_package(
    *,
    work_dir: Path,
    output_dir: Path,
    topic: str,
    date_str: str | None = None,
    providers: dict[str, str],
    stage_durations: dict[str, float],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = date_str or date.today().isoformat()
    slug = slugify(topic)
    base = _free_base(output_dir, f"{date_str}-{slug}")

    outline = Outline.model_validate_json((work_dir / "outline.json").read_text(encoding="utf-8"))
    script = Script.model_validate_json((work_dir / "script.json").read_text(encoding="utf-8"))
    timing = Timing.model_validate_json((work_dir / "timing.json").read_text(encoding="utf-8"))

    final_mp3 = output_dir / f"{base}.mp3"
    final_html = output_dir / f"{base}.html"
    final_transcript = output_dir / f"{base}.transcript.md"
    final_outline = output_dir / f"{base}.outline.json"
    final_manifest = output_dir / f"{base}.manifest.json"

    shutil.copy(work_dir / "episode.mp3", final_mp3)
    shutil.copy(work_dir / "outline.json", final_outline)

    html = (work_dir / "episode.html").read_text(encoding="utf-8")
    html = html.replace('src="episode.mp3"', f'src="{base}.mp3"')
    final_html.write_text(html, encoding="utf-8")

    final_transcript.write_text(_build_transcript(script, timing), encoding="utf-8")

    manifest = _build_manifest(
        topic=topic,
        date_str=date_str,
        slug=slug,
        providers=providers,
        stage_durations=stage_durations,
        outline=outline,
        script=script,
        timing=timing,
        mp3_bytes_size=final_mp3.stat().st_size,
    )
    final_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return final_manifest
