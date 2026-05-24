"""audio-learn CLI entry point."""
from __future__ import annotations

import argparse
import shutil
import sys
import time
import uuid
from datetime import date
from pathlib import Path

from hubed_audio_learn import __version__
from hubed_audio_learn.config import Config, load_config
from hubed_audio_learn.logging_utils import StageLogger
from hubed_audio_learn.pipeline.html_render import run_html_render
from hubed_audio_learn.pipeline.outline import run_outline
from hubed_audio_learn.pipeline.package import run_package
from hubed_audio_learn.pipeline.research import run_research
from hubed_audio_learn.pipeline.script import run_script
from hubed_audio_learn.pipeline.tts import run_tts
from hubed_audio_learn.providers.llm import load_llm_provider
from hubed_audio_learn.providers.tts import load_tts_provider

_LENGTH_MAP = {"s": "short", "m": "medium", "l": "long",
               "short": "short", "medium": "medium", "long": "long"}


def _classify_inputs(inputs: list[str]) -> tuple[str, list[Path]]:
    """Auto-detect doc paths vs. topic words. Returns (topic, doc_paths)."""
    docs: list[Path] = []
    topic_words: list[str] = []
    for item in inputs:
        p = Path(item)
        if p.exists() and p.is_file() and p.suffix.lower() in {".pdf", ".md", ".txt", ".rst"}:
            docs.append(p)
        else:
            topic_words.append(item)
    return " ".join(topic_words).strip(), docs


def _cmd_version(_args: argparse.Namespace) -> int:
    print(f"audio-learn {__version__}")
    return 0


def _cmd_doctor(_args: argparse.Namespace) -> int:
    cfg = load_config()
    print(f"audio-learn version: {__version__}")
    print(f"LLM provider:        {cfg.llm_provider}")
    print(f"TTS provider:        {cfg.tts_provider}")
    print(f"OUTPUT_DIR:          {cfg.output_dir}")
    print(f"WORK_DIR:            {cfg.work_dir}")

    issues = 0
    if cfg.gemini_api_key:
        print("GEMINI_API_KEY: set")
    else:
        print("GEMINI_API_KEY: MISSING (required for tts_provider=gemini)")
        issues += 1

    claude_path = shutil.which(cfg.claude_bin)
    if claude_path:
        print(f"claude binary: {claude_path}")
    else:
        print(f"claude binary: NOT FOUND on PATH (looked for '{cfg.claude_bin}')")
        issues += 1

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"ffmpeg: {ffmpeg_path}")
    else:
        print("ffmpeg: NOT FOUND (required by pydub for MP3 encoding)")
        issues += 1

    return 0 if issues == 0 else 1


def _cmd_podcast(args: argparse.Namespace) -> int:
    cfg = load_config()

    topic, docs = _classify_inputs(args.inputs)
    if not topic:
        print("error: a topic is required (free-form words, not just file paths)", file=sys.stderr)
        return 2

    length = _LENGTH_MAP.get(args.length, "medium")
    episode_id = uuid.uuid4().hex[:10]
    work_dir = cfg.work_dir / episode_id
    work_dir.mkdir(parents=True, exist_ok=True)

    llm = load_llm_provider(cfg.llm_provider, claude_bin=cfg.claude_bin)
    tts = load_tts_provider(cfg.tts_provider, api_key=cfg.gemini_api_key, model=cfg.gemini_tts_model)

    durations: dict[str, float] = {}

    def _timed(stage: str, fn, *args, **kwargs):
        t0 = time.monotonic()
        logger = StageLogger(stage, episode_id)
        logger.event("start")
        result = fn(*args, **kwargs)
        durations[stage] = round(time.monotonic() - t0, 3)
        logger.event("done", elapsed_seconds=durations[stage])
        return result

    _timed("research", run_research,
           topic=topic, user_prompt=args.prompt, user_doc_paths=docs,
           work_dir=work_dir, llm=llm, timeout_seconds=cfg.claude_timeout_seconds)
    _timed("outline", run_outline,
           work_dir=work_dir, target_length=length, user_prompt=args.prompt, llm=llm,
           timeout_seconds=cfg.claude_timeout_seconds)
    _timed("script", run_script,
           work_dir=work_dir, target_length=length,
           host_a_name=cfg.host_a_name, host_a_voice=f"gemini:{cfg.host_a_voice}",
           host_b_name=cfg.host_b_name, host_b_voice=f"gemini:{cfg.host_b_voice}",
           llm=llm, timeout_seconds=cfg.claude_timeout_seconds)
    _timed("tts", run_tts, work_dir=work_dir, tts=tts)
    _timed("html_render", run_html_render, work_dir=work_dir, mp3_filename="episode.mp3")

    manifest_path = _timed("package", run_package,
                           work_dir=work_dir, output_dir=cfg.output_dir,
                           topic=topic, date_str=date.today().isoformat(),
                           providers={"llm": cfg.llm_provider, "tts": cfg.tts_provider},
                           stage_durations=durations)
    print(f"\nDone. Manifest: {manifest_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audio-learn", description="Generate learning podcasts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_podcast = sub.add_parser("podcast", help="Generate a two-host podcast.")
    p_podcast.add_argument("inputs", nargs="+", help="Topic words and/or paths to .pdf/.md/.txt/.rst files.")
    p_podcast.add_argument("--length", choices=list(_LENGTH_MAP.keys()), default="medium")
    p_podcast.add_argument("--prompt", default=None, help="Optional steering prompt for the LLM.")
    p_podcast.set_defaults(func=_cmd_podcast)

    p_version = sub.add_parser("version", help="Print the audio-learn version.")
    p_version.set_defaults(func=_cmd_version)

    p_doctor = sub.add_parser("doctor", help="Check configuration and dependencies.")
    p_doctor.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
