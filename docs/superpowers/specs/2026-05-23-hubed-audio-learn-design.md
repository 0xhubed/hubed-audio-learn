# hubed-audio-learn — Design

- **Status:** draft (awaiting user review before implementation planning)
- **Date:** 2026-05-23
- **Owner:** Daniel Huber
- **Repo:** `hubed-audio-learn` (new, public, MIT) — separate from `hubed-wiki`

## Summary

A standalone learning-artifact generator. Given a topic, a set of documents, or a free-form prompt, it researches the subject and produces an educational artifact in one of two forms:

1. **Podcast mode** (default): a two-host conversational MP3 plus an interactive HTML player with slide-style figures that auto-sync to the audio.
2. **Doc mode** (opt-in): a printable PDF written as prose, with math, figures, and source citations.

The pipeline shares a single research pass and a canonical content outline between both modes. The tool is provider-agnostic: a default cloud configuration (Claude for reasoning, Gemini 2.5 native audio for TTS) and an opt-in open-source configuration (an OpenAI-compatible LLM endpoint, Nari Labs Dia-1.6B for TTS) coexist behind clean interfaces. The CLI is the primary surface; an optional Telegram bot ships in the same repo behind environment-variable gates.

## Goals

- One-command generation of a polished, structured learning artifact from a topic name, a set of source documents, or a prompt.
- High-quality two-host conversational audio out of the box (NotebookLM-style listening experience).
- An interactive HTML companion that auto-syncs slides to the current moment in the audio.
- Optional PDF "document mode" for users who want to read rather than listen.
- Provider abstraction that supports running entirely on open-source models for cost or independence reasons.
- Reusable in a corporate setting: configurable via env vars, no hardcoded personal paths, MIT-licensed, no required external SaaS dependencies in the OSS configuration.

## Non-goals

- Bilingual / multilingual output. English only. (Reconsider in a later version if there is demand.)
- Video output (MP4 / Manim animations). Dropped from scope.
- PowerPoint (`.pptx`) output. May be added later by writing one additional renderer against the same outline contract; not in v1.
- Hosted distribution (RSS feeds, podcast directories, web UI for browsing past episodes). Out of scope. Episodes drop into a synced folder; downstream sync is the user's responsibility.
- Knowledge-base coupling. The tool does not read from or write to `hubed-wiki` or any other knowledge store. A user who wants to feed wiki content into the tool can do so by passing source files explicitly to the CLI.
- Real-time / streaming generation. The tool runs to completion per episode and writes finished artifacts.

## Background and motivation

The user already maintains `hubed-wiki`, a Claude-powered personal knowledge base accessed through Telegram and Obsidian Sync. The wiki is excellent for capture and reference but does not address a separate workflow: turning a topic into a structured listening or reading experience for self-paced learning. NotebookLM popularized the two-host podcast format; this project brings the same capability under the user's own control, with the option to swap in open-source models, deploy in a company environment, and produce written documents as an alternative artifact.

A separate repo (rather than extending `hubed-wiki`) is justified by three considerations: the repo will be public and reusable in a company setting (the wiki is private), the pipeline shares no code with the wiki bot, and keeping the wiki's purpose sharp (curated knowledge base) is more valuable than the small infrastructure savings of co-location.

## Architecture overview

### Repo layout

```
hubed-audio-learn/
├── README.md
├── LICENSE                       # MIT
├── pyproject.toml                # package: hubed-audio-learn, console_script: audio-learn
├── .env.example
├── src/hubed_audio_learn/
│   ├── cli.py
│   ├── config.py
│   ├── pipeline/
│   │   ├── research.py
│   │   ├── outline.py
│   │   ├── script.py
│   │   ├── prose.py
│   │   ├── tts.py
│   │   ├── html_render.py
│   │   ├── pdf_render.py
│   │   └── package.py
│   ├── providers/
│   │   ├── llm/
│   │   │   ├── base.py
│   │   │   ├── claude.py
│   │   │   └── openai_compatible.py
│   │   └── tts/
│   │       ├── base.py
│   │       ├── gemini.py
│   │       └── dia.py
│   ├── schemas/                  # pydantic models for the JSON contracts
│   ├── prompts/                  # script-gen, outline-gen, prose-gen templates
│   └── templates/
│       ├── html/                 # Jinja player template + vendored KaTeX
│       └── pdf/                  # Jinja print stylesheet + vendored KaTeX
├── bot/
│   └── bot.py                    # OPTIONAL Telegram frontend, env-gated
├── services/                     # systemd unit templates
├── docs/
└── tests/
```

### Pipeline

The pipeline has six stages. Each stage reads its inputs from disk and writes its outputs to disk in a working directory (`./.work/{episode_id}/`). Stages are independent processes invoked in sequence by the CLI.

```
input ──▶ research ──▶ research_bundle.json
                 │
                 ▼
              outline.json    (canonical content tree:
                               sections, key_claims, figures, sources)
                 │
        ┌────────┴────────┐
        ▼                 ▼
  podcast path        doc path
  ────────────        ────────
  script.json          document.json
       │                    │
       ▼                    ▼
  tts → episode.mp3    pdf_render → episode.pdf
       + timing.json
       │
       ▼
  html_render → episode.html

  ───────────────────────────────────────────────
  package → moves final artifacts into OUTPUT_DIR
```

The split between podcast and doc paths is selected by the CLI subcommand. The `both` subcommand runs the shared front end once and then both render paths; this is cheaper than running `podcast` and `doc` separately because the expensive research and outline steps are amortized.

### Data contracts

All four intermediate JSON files are validated against pydantic schemas on read and on write. The schemas live in `src/hubed_audio_learn/schemas/` and are the canonical contract between stages.

#### `research_bundle.json`

```json
{
  "topic": "Kalman filters",
  "user_prompt": "Explain intuitively, then go deep into the math.",
  "user_docs": [{"path": "kalman-paper.pdf", "kind": "pdf", "extracted_text": "..."}],
  "web_sources": [
    {"url": "https://en.wikipedia.org/wiki/Kalman_filter",
     "title": "Kalman filter — Wikipedia",
     "fetched_at": "2026-05-23T10:14:00Z",
     "content": "..."}
  ],
  "search_queries_used": ["Kalman filter intuition", "Kalman filter prediction step"]
}
```

#### `outline.json` — canonical content tree

```json
{
  "topic": "Kalman filters",
  "language": "en",
  "target_length": "medium",
  "audience_assumed": "ML engineer comfortable with linear algebra",
  "learning_objectives": ["Build intuition for the prediction-correction loop", "..."],
  "sections": [
    {
      "id": "intro",
      "title": "Why Kalman filters exist",
      "summary": "Motivate with a sensor-fusion example.",
      "key_claims": [
        {"text": "Sensors are noisy; combining estimates beats either alone.",
         "sources": ["wikipedia:Kalman_filter#History"]}
      ],
      "examples": [{"kind": "scenario", "body": "A car estimating its position..."}],
      "figures": [
        {"id": "fig-scenario-car", "kind": "diagram",
         "caption": "Car position estimated from GPS + wheel encoder"}
      ]
    },
    {
      "id": "prediction",
      "title": "The prediction step",
      "key_claims": [{"text": "...", "sources": []}],
      "examples": [],
      "figures": [
        {"id": "fig-predict", "kind": "math-block",
         "latex": "\\hat{x}_{k|k-1} = F_k \\hat{x}_{k-1|k-1} + B_k u_k",
         "caption": "State propagation"}
      ]
    }
  ],
  "sources_used": [{"id": "wikipedia:Kalman_filter", "url": "...", "title": "..."}]
}
```

Section ids are stable across the script and document, so an HTML slide and a PDF heading for the same outline section share an identifier.

#### `script.json` — podcast path

```json
{
  "outline_ref": "outline.json",
  "host_a": {"name": "Alex", "voice_id": "gemini:Charon", "persona": "curious-host"},
  "host_b": {"name": "Sam",  "voice_id": "gemini:Leda",   "persona": "explainer"},
  "turns": [
    {"speaker": "A", "text": "So today we're tackling Kalman filters...",
     "section_ref": "intro"},
    {"speaker": "B", "text": "Right — imagine you're trying to estimate where a car is...",
     "section_ref": "intro",
     "slide_marker": {"figure_id": "fig-scenario-car", "cue": "soft"}}
  ]
}
```

The TTS stage produces a sibling `timing.json` mapping turn index → start-seconds:

```json
{"turns": [{"index": 0, "start_seconds": 0.00},
           {"index": 1, "start_seconds": 4.83}]}
```

#### `document.json` — doc path

```json
{
  "outline_ref": "outline.json",
  "title": "A Primer on Kalman Filters",
  "sections": [
    {
      "id": "intro",
      "title": "Why Kalman filters exist",
      "paragraphs": ["Imagine a car that knows where it was a second ago...", "..."],
      "figures_inline": ["fig-scenario-car"]
    }
  ],
  "bibliography": [{"id": "wikipedia:Kalman_filter", "citation": "..."}]
}
```

## Components

### `research.py`

Takes `topic`, optional `user_prompt`, and optional `user_docs` paths. Produces `research_bundle.json`.

Two implementations dispatched at runtime by `LLM_PROVIDER`:

- **Claude path (`LLM_PROVIDER=claude`, default).** Shells out to `claude --print` with `--allowedTools WebFetch,WebSearch,Read`. Claude drives the research loop internally — proposes queries, fetches pages, synthesizes. Reuses the proven pattern from `hubed-wiki/bot/bot.py`.
- **OpenAI-compatible path (`LLM_PROVIDER=openai_compatible`).** Drives the loop in Python:
  1. Ask the LLM for 3–5 search queries given the topic and user prompt.
  2. Execute each query via a search API. Tavily is the default (`TAVILY_API_KEY` env var); a `searx` fallback or DuckDuckGo HTML scrape is acceptable for fully-OSS deployments.
  3. Fetch the top hits with `httpx` and extract main content with `readability-lxml`.
  4. Ask the LLM to synthesize into the bundle.

Both paths produce identical `research_bundle.json`. PDFs in `user_docs` are parsed with `pypdf`. Plain text and Markdown files pass through. URLs in the input are treated as `web_sources` seeds.

### `outline.py`

One LLM call. Input: the research bundle, the user prompt, the target length. Output: `outline.json`.

The LLM is prompted to emit JSON matching the outline schema. Output is parsed and validated with pydantic. On validation failure, retry once with the validator's error message appended to the prompt. Two failures → raise.

### `script.py`

One LLM call. Input: `outline.json` + target length + host personas (from config). Output: `script.json`.

Prompt structure: "Convert this outline into a two-host conversation. Host A is curious and asks questions; Host B is the explainer. Reference figures by `figure_id` at the moment they should appear via `slide_marker`. Keep turns short (2–4 sentences). Target N words for `length=medium`." Validation as in `outline.py`.

### `prose.py`

One LLM call. Input: `outline.json`. Output: `document.json`.

Prompt structure: "Convert this outline into a written primer suitable for reading. Use headings matching `sections[].title`. Inline figures by `figure_id` where appropriate. Cite sources with footnote-style refs." Validation as in `outline.py`.

### `tts.py` + `providers/tts/`

`tts.py` is a thin dispatcher:

```python
provider = load_tts_provider(config.TTS_PROVIDER)
mp3_bytes, timing = provider.render(script_json)
```

The `TTSProvider` abstract base class declares:

```python
class TTSProvider(ABC):
    name: str
    supported_languages: list[str]  # ["en"] for now; future-proofs DE

    @abstractmethod
    def render(self, script: ScriptJson) -> tuple[bytes, TimingJson]:
        """Render the dialogue script to MP3 bytes + per-turn timing."""
```

**`providers/tts/gemini.py`** — uses the `google-genai` SDK in multi-speaker audio mode. Submits the full script as a single dialogue payload with `[S1]`/`[S2]` tags; receives a single audio stream with per-turn segment offsets. Timing is taken directly from the API response. Voice IDs configurable (default `Charon` for Host A, `Leda` for Host B).

**`providers/tts/dia.py`** — uses `transformers` to load `nari-labs/Dia-1.6B` on first use. Builds the prompt as `[S1] turn1 [S2] turn2 ...`; runs one forward pass; receives the full conversation audio. Timing is recovered by aligning turn boundaries to silence detection (`librosa.effects.split` on the output waveform) — fuzzy but adequate for slide-sync UX. Hard-errors with a clear message if no CUDA device is detected.

Both providers produce identical outputs (`episode.mp3` + `timing.json`).

### `html_render.py`

Jinja template produces a single self-contained HTML file referencing the sibling MP3. Top of page: an `<audio controls>` element. Below: a vertical stack of "slides", one per unique `figure_id` referenced in `script.json`. Each slide renders its outline figure (math via inline KaTeX, scenario boxes, plain text, etc.).

Inline JavaScript (~50 lines):

- Listens to `audio.timeupdate`.
- Uses the embedded `timing.json` to find the current turn → looks up its `slide_marker.figure_id` → toggles `.active` class on the corresponding slide and scrolls it into view.
- Tapping a slide seeks `audio.currentTime` to that slide's first-occurrence start time.
- URL fragment `#t=04:32` parsed on load and applied to `audio.currentTime`.

No build step, no npm. KaTeX CSS/JS vendored under `templates/html/vendor/` (~150 KB total). The output HTML works offline.

### `pdf_render.py`

Same approach with a different Jinja template tuned for print: page breaks per section, no audio player, footnotes for sources, vendored KaTeX. Rendered to PDF via Playwright headless Chromium (`page.pdf()`).

Playwright is a heavy dependency (~300 MB Chromium binary). Installed lazily: the `pdf_render` module imports Playwright at call time, and the README documents `playwright install chromium` as a one-time setup step. Users who only run `audio-learn podcast` never need it.

### `package.py`

Moves final artifacts from `./.work/{episode_id}/` to `OUTPUT_DIR` under the naming scheme `{YYYY-MM-DD}-{slug}.{mp3,html,transcript.md,pdf,outline.json}`. Also produces `transcript.md` from `script.json` + `timing.json`: a plain-Markdown rendering of the dialogue with one block per turn, prefixed by `[mm:ss] HostName:`, with a bibliography section at the end. Writes `manifest.json` next to them with:

- Providers and model versions used
- Token counts (when available)
- TTS character counts
- Wall-clock time per stage
- Estimated cost (computed from provider rates when known)
- Source citations

The slug is derived from the topic via `python-slugify`.

## Providers

### LLM providers

`LLMProvider.generate(prompt: str, **opts) -> str` is the single method on the abstract base class.

- **`providers/llm/claude.py`** — Default. Shells out to `claude --print` with configurable timeout. Tools allowed depend on the stage; `research.py` enables `WebFetch,WebSearch,Read`; other stages allow no tools (pure text generation).
- **`providers/llm/openai_compatible.py`** — Wraps the `openai` Python SDK pointed at a configurable `OAI_BASE_URL` and `OAI_MODEL`. Works with vLLM, Ollama, LM Studio, the real OpenAI API, the user's company Gemma-3 27B MoE deployment, and most other modern LLM servers.

### TTS providers

Discussed above. Both implement `TTSProvider`. New providers (ElevenLabs, PlayHT, Sesame CSM, Kokoro, etc.) can be added by writing one file conforming to the interface.

## CLI surface

```
audio-learn podcast <input...> [--length s|m|l] [--llm ...] [--tts ...] [--out DIR] [--max-cost-usd N] [--verbose] [--resume]
audio-learn doc     <input...> [--length s|m|l] [--llm ...]              [--out DIR] [--max-cost-usd N] [--verbose] [--resume]
audio-learn both    <input...> [--length s|m|l] [--llm ...] [--tts ...] [--out DIR] [--max-cost-usd N] [--verbose] [--resume]
audio-learn render --html  --from PATH/episode.outline.json [--out DIR]
audio-learn render --pdf   --from PATH/episode.outline.json [--out DIR]
audio-learn version
audio-learn doctor                       # prints config, checks for API keys, GPU, Chromium
```

`<input...>` is one or more arguments, each of which is auto-detected as:

- A URL — fetched as a web source seed.
- A local path ending in `.pdf` — parsed and treated as a user doc.
- A local path ending in `.md`, `.txt`, or `.rst` — read as a user doc.
- Anything else — concatenated as the topic / prompt.

`--length` defaults to `medium` (~15–25 min target). `--llm` and `--tts` default to the env-configured providers. `--out` defaults to `$OUTPUT_DIR` from env or `./output/`. `--max-cost-usd` halts before TTS if the estimated cost exceeds the budget. `--resume` skips any stage whose output already exists in the working dir.

## Optional Telegram bot

Mirrors the wiki bot's structure (Daniel's existing `hubed-wiki/bot/bot.py` pattern). Active only when both `TELEGRAM_BOT_TOKEN` and `ALLOWED_USER_IDS` are set in the environment; otherwise the module is dormant.

Behavior: receive a message, classify it (`/podcast`, `/doc`, `/both`, or natural-language intent), shell out to the CLI, send back the finished artifact filenames. With synced-folder delivery, the bot only needs to confirm "Episode ready: 2026-05-23-kalman-filters.mp3" — the file itself reaches the phone via Syncthing or Obsidian Sync.

The bot is in `bot/` rather than `src/hubed_audio_learn/bot/` to make it clear it's an optional frontend, not part of the library.

## Output and delivery

Episodes land in `OUTPUT_DIR` (default `./output/`, conventionally configured to a synced folder like `~/Podcasts/`).

Per request, the following files are written (a subset depending on subcommand):

```
2026-05-23-kalman-filters.mp3              # podcast/both
2026-05-23-kalman-filters.html             # podcast/both (interactive player)
2026-05-23-kalman-filters.transcript.md    # podcast/both
2026-05-23-kalman-filters.pdf              # doc/both
2026-05-23-kalman-filters.outline.json     # always (enables cheap re-renders)
2026-05-23-kalman-filters.manifest.json    # always (audit trail)
```

The user's phone picks up new files via Syncthing or Obsidian Sync. No HTTP server, no RSS feed, no external surface area in v1.

## Error handling

- Each stage validates its input against a pydantic schema on entry. Bad input → fail loudly with the validation error; do not attempt to repair.
- LLM calls have one retry on JSON-validation failure (validator error message appended to the prompt). Two failures → raise.
- Web research retries each search query twice with exponential backoff (1s, 4s). On final failure, the query is dropped and noted in `research_bundle.json`; the pipeline continues.
- TTS API calls retry three times with backoff and respect `Retry-After`. Final failure raises.
- Dia provider with no CUDA device: hard error with a clear message. No silent CPU fallback (would be impractically slow).
- Stages are independent processes; a crash in stage N leaves stage N-1's outputs intact on disk.

## Resumability

A working directory per episode (`./.work/{episode_id}/`) holds every intermediate JSON. The CLI's `--resume` flag skips any stage whose output file already exists. The `audio-learn render` subcommand uses this implicitly: it locates a previously-generated `outline.json` and re-runs only the requested renderer.

## Observability

- **Structured logs** to stdout as JSONL. Each event: `{ts, stage, episode_id, event, data}`.
- **`manifest.json` per episode** — providers, model versions, token counts (when available), TTS character counts, per-stage wall-clock time, estimated cost, source citations.
- **`--verbose`** dumps full LLM prompts and raw responses to the working dir for debugging.
- No metrics backend, no tracing. The JSONL logs ship cleanly into any downstream system if needed.

## Testing

Three layers, each gated by a pytest marker:

1. **Unit (always run, fast, no network).** Schema validation, prompt rendering, HTML/PDF template snapshots, CLI argument parsing.
2. **Provider contract (`pytest -m provider`).** One small real call per provider checking output shape. ~$0.01 per run. CI runs on tagged releases only.
3. **End-to-end smoke (`pytest -m e2e`).** Generates one short episode on a fixed topic with the default providers and asserts the output files exist and are non-empty. Manual trigger only.

No mocked-LLM tests beyond schema validation. Either we test the real provider or we test the surrounding code with the LLM call factored out.

## Cost and rate-limit handling

The TTS dispatcher computes an estimated cost from the script's character count and the provider's published rate before submitting the call. If `--max-cost-usd` is set and the estimate exceeds the budget, the CLI prompts for confirmation (or aborts if running non-interactively).

The `manifest.json` records actual token and character counts and the resulting cost estimate for every run.

Rate-limit handling lives in each provider — they respect `Retry-After` headers and back off. Cross-provider quota tracking is out of scope; users running into quotas should rotate providers via `--tts`.

## MVP cut (Phase 1)

The first shipping version targets a working `audio-learn podcast` end-to-end on the default providers. Specifically:

- `research.py` Claude-path only (skip the OpenAI-compatible loop)
- `outline.py`, `script.py`
- `tts.py` + `providers/tts/gemini.py` only
- `html_render.py`
- `package.py`
- `cli.py` with the `podcast` subcommand and `version`, `doctor`
- Tests at layer 1 (unit)
- `README.md`, `.env.example`, one working example invocation

Phase 1 success criterion: from a fresh checkout, `pip install -e .`, set `GEMINI_API_KEY`, run `audio-learn podcast "Kalman filters" --length medium`, and end up with a synced MP3 + HTML in the output dir that plays correctly on a phone with audio↔slide sync working.

## Phase 2 (separate plan)

Everything else, prioritized by what real usage reveals first:

- `prose.py` + `pdf_render.py` + `audio-learn doc` / `both` subcommands
- `providers/llm/openai_compatible.py` + the manual research loop
- `providers/tts/dia.py`
- The Telegram bot (`bot/bot.py`)
- Provider contract tests
- `--resume` and `audio-learn render` from cached outline

Each Phase-2 item is independently mergeable.

## Open questions

- **Search backend for the OSS research path.** Tavily is the default for v1 of Phase 2. Worth evaluating Brave Search API and self-hosted SearXNG as alternatives. The choice is a config knob, not a code change.
- **Host persona prompts.** The default Alex/Sam personas are placeholders. Iteration on persona prompts is expected after the first few real episodes; this is content-tuning, not architecture.
- **Slide visual style.** The HTML/PDF templates need a real design pass. v1 ships a functional minimal style; a polished theme is post-MVP.
- **Cost estimation accuracy.** Provider rates change; the cost table will need periodic updates. Mitigated by treating `--max-cost-usd` as a soft guardrail, not a billing system.

## Appendix: example session

The session below shows the full intended product surface. Commands marked **(Phase 2)** are not in the v1 MVP cut.

```bash
# Initial setup (Phase 1)
git clone <repo-url>
cd hubed-audio-learn
pip install -e .
cp .env.example .env
# edit .env: set GEMINI_API_KEY, OUTPUT_DIR=~/Podcasts/

# Generate a medium-length podcast on a topic (Phase 1)
audio-learn podcast "Kalman filters" --length medium

# → researches, outlines, scripts, TTS, renders HTML
# → writes to ~/Podcasts/2026-05-23-kalman-filters.{mp3,html,transcript.md,outline.json,manifest.json}

# Listen on phone via Syncthing-synced folder.

# Later, decide you also want the PDF (Phase 2)
audio-learn render --pdf --from ~/Podcasts/2026-05-23-kalman-filters.outline.json
# → writes 2026-05-23-kalman-filters.pdf next to the others. No re-research.

# Generate both formats at once for a new topic, capping cost (Phase 2 for `both`; --max-cost-usd is Phase 1)
audio-learn both "Transformer attention" --length long --max-cost-usd 2.00
```
