# hubed-audio-learn

A standalone learning-artifact generator. Given a topic, documents, or a prompt, it researches the subject and produces either a two-host conversational podcast (MP3 + interactive HTML player with synced slides) or a printable PDF primer. Public repo, MIT-licensed, English-only in v1.

## Status

**Phase 1 MVP implemented; not yet run live.** The full podcast pipeline exists under `src/hubed_audio_learn/` (research → outline → script → tts → html_render → package), plus the `audio-learn` CLI (`podcast`/`version`/`doctor`). 42 unit tests pass (`pytest`); real-provider/e2e tests are gated behind the `provider` and `e2e` markers and have **not** been run — no stage has been exercised against a live Claude/Gemini call. The implementation plan is at [docs/superpowers/plans/2026-05-24-phase1-mvp.md](docs/superpowers/plans/2026-05-24-phase1-mvp.md).

## Canonical reference

The authoritative design document is [docs/superpowers/specs/2026-05-23-hubed-audio-learn-design.md](docs/superpowers/specs/2026-05-23-hubed-audio-learn-design.md). Read it before doing anything else in this repo — it covers architecture, data contracts, components, providers, CLI surface, error handling, testing, and the Phase 1 / Phase 2 split.

## Quick orientation for new Claude sessions

- **Language:** Python (CLI tool + library).
- **Package name:** `hubed-audio-learn` (PyPI); module: `hubed_audio_learn`; CLI binary: `audio-learn`.
- **Default providers:** Claude (LLM, via `claude --print`) + Gemini 2.5 native audio (TTS).
- **Opt-in OSS path:** any OpenAI-compatible LLM endpoint + Nari Labs Dia-1.6B (requires CUDA; the user has a DGX Spark for this).
- **Output:** drops files into a configurable directory (`OUTPUT_DIR`, default `./output/`); intended to be a Syncthing- or Obsidian-Sync-synced folder so episodes appear on the phone automatically.
- **No HTTP server, no RSS feed, no wiki coupling, no video.**

## Phase 1 MVP scope

The first shipping version is intentionally narrow — see the spec's "MVP cut" section. Roughly:

- `research.py` (Claude path only) → `outline.py` → `script.py` → `tts.py` (Gemini only) → `html_render.py` → `package.py`
- CLI: `audio-learn podcast <input...> [--length s|m|l]` plus `version` and `doctor`
- Unit tests only; real-provider tests gated behind a marker
- README, `.env.example`, one working example

Phase 1 success criterion: from a fresh checkout, `pip install -e .`, set `GEMINI_API_KEY`, run `audio-learn podcast "Kalman filters" --length medium`, and end up with a synced MP3 + HTML in the output dir that plays correctly with audio↔slide sync working.

## Related project

`hubed-wiki` (separate private repo at `~/Documents/projects/hubed-wiki`) is the user's existing Claude-powered knowledge base. The two projects intentionally do not share code; the design rationale for separation is in the spec under "Background and motivation".

## Next step

Run the Phase 1 success criterion live: from a fresh checkout, `pip install -e .`, set `GEMINI_API_KEY`, run `audio-learn podcast "Kalman filters" --length medium`, and confirm a synced MP3 + HTML lands in `OUTPUT_DIR` with audio↔slide sync working. `docs/smoke-test.md` is the checklist for that run.

Open code-review findings are tracked in [docs/review-2026-05-24.md](docs/review-2026-05-24.md). The High/cheap items #1 (`.envrc` gitignore), #3 (Claude markdown-fence stripping), #5 (no-clobber on re-run), and #9 (UTF-8 subprocess encoding) are **done**. Remaining deferred items: #2 (`</script>` escaping in the HTML template), #4 (Gemini response guards), #6 (fragile silence-detection timing), #7 (script↔outline referential integrity), #8 (`audio_duration_estimate_seconds` mislabel), #10 (fragile HTML `src` rewrite).
