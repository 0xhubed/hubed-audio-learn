# Phase 1 smoke test

First end-to-end live run of `audio-learn podcast` against real Claude + Gemini.

Mirror of `docs/smoke-test.html` in plain markdown so it's easy to follow at the
terminal. Tick items off in your head (or your editor) as you go.

**Budget:** ~$0.10 of Gemini quota + a few cents of Claude. Wall time ~3–6 min
for a `short` episode.

---

## 0. Heads-up — known landmines before you start

From the code review (`docs/review-2026-05-24.md`) — none of these were fixed
before the smoke test. Watch for them; the run is also a confirmation that
these are the priorities for Phase 2.

1. **Most likely first-run blocker (review §3):** `claude --print` sometimes
   wraps JSON in ` ```json … ``` ` fences. `ClaudeProvider.generate` does not
   strip them, so research/outline/script may die with
   `... stage failed after 2 attempts`. If you hit this, the one-line fix is
   in `docs/review-2026-05-24.md` §3 — apply it locally, do **not** commit
   from the smoke-test branch.
2. **Security (review §1):** `.envrc` is not in `.gitignore`. If you use
   `direnv`, do **not** put `GEMINI_API_KEY` in `.envrc` for this repo — it
   could leak on `git add -A`. Use `.env` only.
3. **Silent overwrite (review §5):** rerunning the same topic the same day
   clobbers the previous episode. If you re-run, rename the first output
   first.

---

## 1. System prerequisites

```bash
# Python 3.11+
python3 --version

# ffmpeg (pydub needs it to encode PCM → MP3)
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Debian/Ubuntu
which ffmpeg

# Claude Code CLI (research stage shells out to it)
which claude
claude --version
```

You also need a Gemini API key — get one at
<https://aistudio.google.com/apikey>. Free tier is fine for one run.

---

## 2. Repo setup

```bash
cd ~/Documents/projects/hubed-audio-learn
git status                   # clean tree, on main
source .venv/bin/activate
pip install -e ".[dev]"      # idempotent
```

Create `.env`:

```bash
cp .env.example .env
# Edit .env — at minimum:
#   GEMINI_API_KEY=<your key>
# Optionally:
#   OUTPUT_DIR=~/Podcasts/    # any Syncthing/Obsidian-Sync folder
```

Never commit `.env`. See landmine #2 above re `.envrc`.

---

## 3. Verify config

```bash
audio-learn doctor
```

Expect roughly:

```
audio-learn version: 0.1.0
LLM provider:        claude
TTS provider:        gemini
OUTPUT_DIR:          /abs/path/output
WORK_DIR:            /abs/path/.work
GEMINI_API_KEY: set
claude binary: /opt/homebrew/bin/claude
ffmpeg: /opt/homebrew/bin/ffmpeg
```

Exit code 0. If anything says `MISSING` or `NOT FOUND`, fix it before
proceeding — those gates are pre-conditions for the live run.

---

## 4. Run the smoke episode

```bash
audio-learn podcast "Kalman filters" --length short
```

Why `short`: ~1200 words, ~5–8 min of audio — fail fast and cheaply on the
first run. Promote to `medium` once it works end-to-end.

You should see JSONL on stdout, one block per stage:

```
{"ts":..., "stage":"research", "event":"start", ...}
{"ts":..., "stage":"research", "event":"done",  "data":{"elapsed_seconds":42.1}}
{"ts":..., "stage":"outline",  "event":"start", ...}
…
Done. Manifest: /abs/path/output/2026-05-28-kalman-filters.manifest.json
```

Stage timings, rough first-run baseline:

- `research`  30–90 s  (Claude WebSearch + WebFetch)
- `outline`   ~10 s
- `script`    ~20 s
- `tts`       30–60 s  (Gemini, then librosa silence-detect, then ffmpeg)
- `html_render` + `package`  <1 s

If a stage hangs >10 min: Ctrl-C, inspect `./.work/<episode_id>/` to see the
last successfully-written JSON. Phase 1 is **not** resumable — you'll restart
from scratch. That's a known limitation.

### Failure modes to recognise on sight

| Symptom                                            | Likely cause                       | Fix                                                       |
|----------------------------------------------------|------------------------------------|-----------------------------------------------------------|
| `research stage failed after 2 attempts`           | Review §3 — Claude JSON fences     | Apply patch from `docs/review-2026-05-24.md` §3           |
| `IndexError`/`AttributeError` in `tts` stage       | Review §4 — Gemini empty candidates| Capture the raw `response` shape; safety filter / quota   |
| `claude: command not found`                        | Claude CLI not on PATH             | Re-run §1                                                 |
| `Couldn't find ffmpeg or avconv`                   | ffmpeg not on PATH                 | Re-run §1                                                 |
| `UnicodeEncodeError` from `subprocess.run`         | Review §9 — non-UTF8 locale        | `export PYTHONIOENCODING=utf-8` and retry                 |

---

## 5. Inspect the artifacts

Use today's date in the filenames (the runtime stamps with the current date).

```bash
ls -la "$OUTPUT_DIR"   # or ls -la output/
```

Expect 5 files for the episode:

```
YYYY-MM-DD-kalman-filters.mp3
YYYY-MM-DD-kalman-filters.html
YYYY-MM-DD-kalman-filters.transcript.md
YYYY-MM-DD-kalman-filters.outline.json
YYYY-MM-DD-kalman-filters.manifest.json
```

Run each check:

```bash
# (1) MP3 plays, two distinct voices
open output/*-kalman-filters.mp3       # macOS
# xdg-open … on Linux
```

Listen to ~30 s. Alex (curious) and Sam (explainer) should alternate cleanly —
no chopping, no garbled audio, no obvious mid-word cuts.

```bash
# (2) HTML player syncs slides to audio
open output/*-kalman-filters.html
```

Play it. As each slide marker triggers, the corresponding figure should get a
blue border and scroll into view. Math should render via KaTeX (CDN-loaded in
Phase 1 — needs internet on first open). Clicking a slide should seek the
audio to that slide's first appearance.

If slide cues drift by more than ~1–2 s, this is review §6
(silence-detection fallback). Peek at `./.work/<episode_id>/timing.json` and
sanity-check whether `start_seconds` matches what you hear.

```bash
# (3) Transcript readable, timestamps monotonic
less output/*-kalman-filters.transcript.md
```

Each block is `[mm:ss] Host:` then the turn text. Timestamps must be
monotonically increasing. Note: `audio_duration_estimate_seconds` in the
manifest is mislabelled (review §8) — it's actually the start of the last
turn, not the full duration. Don't be alarmed if it reads ~30 s shorter than
the MP3.

```bash
# (4) Manifest looks sane
cat output/*-kalman-filters.manifest.json | python -m json.tool
```

Sanity-check:

- `topic` matches what you ran
- `providers.llm == "claude"`, `providers.tts == "gemini"`
- `turn_count > 0`
- `stage_durations_seconds` has all 6 stages
- `sources` has at least one entry (Claude actually fetched web content)

---

## 6. Mobile delivery (optional)

If `OUTPUT_DIR` is inside a Syncthing/Obsidian-Sync folder, wait 30–60 s and
check the phone. All 5 files should appear. Open the HTML in mobile Safari /
Chrome — slide sync should still work (KaTeX needs network on first load).

---

## 7. Capture what you learn

Things to write down (or open issues for) after the run:

- Did **review §3** (Claude code fences) fire? Yes/No — confirms whether it's
  the actual Phase-2 priority it looks like.
- Did **review §6** (slide drift) fire? Note approximate drift in seconds and
  where in the episode.
- Did **review §4** (Gemini error path) fire? If yes, capture the raw
  response — the user-facing error is currently terrible.
- Total wall time for the run.
- Was the listening experience actually useful? (i.e., would you want a
  `medium`/`long` version of this topic?)

If the run is clean: Phase 2 planning can lead with features (PDF input mode,
OSS provider path on the DGX Spark, packaging) over the review hardening
items.

If the run blows up at a specific stage: keep the `.work/<episode_id>/`
directory around — it's the smoke-test post-mortem evidence.
