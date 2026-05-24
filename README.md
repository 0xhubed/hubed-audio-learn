# hubed-audio-learn

Generate a two-host conversational podcast (MP3 + interactive HTML player) from a topic.

Phase 1 MVP: Claude for research and scripting, Gemini 2.5 multi-speaker TTS for audio.

## Install

System prerequisites: Python 3.11+, `ffmpeg` on PATH, the [Claude Code](https://docs.anthropic.com/claude/docs/claude-code) CLI on PATH.

```bash
git clone <repo-url>
cd hubed-audio-learn
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env: set GEMINI_API_KEY at minimum
```

Verify your setup:

```bash
audio-learn doctor
```

## Generate a podcast

```bash
audio-learn podcast "Kalman filters" --length medium
```

The pipeline writes intermediate JSON into `./.work/<episode_id>/` and finished artifacts into `$OUTPUT_DIR` (default `./output/`):

```
2026-05-23-kalman-filters.mp3
2026-05-23-kalman-filters.html              # open in any browser; auto-syncs slides
2026-05-23-kalman-filters.transcript.md
2026-05-23-kalman-filters.outline.json
2026-05-23-kalman-filters.manifest.json
```

To pick the file up on your phone, set `OUTPUT_DIR` to a Syncthing/Obsidian-Sync folder.

## Inputs

`audio-learn podcast` takes one or more positional inputs. Each is auto-classified:

- A path to a `.pdf`, `.md`, `.txt`, or `.rst` file → treated as a user-supplied source document.
- Anything else → concatenated to form the topic.

Examples:

```bash
audio-learn podcast "Diffusion models" --length short
audio-learn podcast "Kalman filters" ./kalman-paper.pdf --prompt "Focus on intuition over math."
```

## Subcommands

- `audio-learn podcast <inputs...> [--length s|m|l] [--prompt TEXT]`
- `audio-learn version`
- `audio-learn doctor`

## Development

```bash
pytest               # unit tests only
pytest -m provider   # real-provider contract tests (Phase 2)
pytest -m e2e        # end-to-end smoke (Phase 2)
```

See `docs/superpowers/specs/2026-05-23-hubed-audio-learn-design.md` for the full design.

## License

MIT.
