# Learning-app frontend: discussion summary

Notes from an exploratory discussion about expanding `hubed-audio-learn` beyond
a Python CLI into a cross-device learning-app experience. **No decisions are
final** — this is a starting point to pick up from, not a spec.

The canonical Phase 1 design ([2026-05-23-hubed-audio-learn-design.md](superpowers/specs/2026-05-23-hubed-audio-learn-design.md))
is unchanged; this document is a forward-looking sketch of what a Phase 2 / 3
might look like and what assumptions in the current spec would need to flip.

## Why we're considering this

The current spec ships a Python CLI that drops files into a synced output
folder. That works for developers. The thought experiment was: could the same
pipeline power a real learning-app experience that non-technical people could
install and use, with mobile-first podcast consumption as the central use case?

## What we want to achieve

A **personal-scale learning tool** that:

- Generates two-host audio "lessons" on demand from a topic / docs / prompt
  (the existing pipeline).
- Is genuinely usable on a phone during a commute — that's the *primary*
  listening context, not desktop.
- Keeps the synced-slides interactive player as a sit-down experience for
  deeper sessions.
- Stays open-source and BYOK. **No hosted SaaS, no subscriptions, no
  per-user backend on our side.**
- Is installable by a curious non-developer (no Docker, no terminal, no
  Python install).

Built for the maintainer first; "people like me" second. Not built for
NotebookLM's or BeFreed's audience.

## The unique angle (what makes this worth building given the competition)

The space is crowded — see [Competitive landscape](#competitive-landscape)
below. The defensible corner that nobody currently occupies:

> **The only OSS learning-podcast tool a non-developer can actually install
> and use on their phone during their commute, with audio↔slide sync as the
> differentiating experience.**

If any of those three constraints drops (OSS, non-developer-installable,
mobile-via-podcast-app), an existing product already serves that audience
better.

## Proposed architectural shape

### Generator: Tauri desktop app

- Signed installers for Mac (`.dmg`) and Windows (`.msi`/`.exe`).
- Bundles the Python pipeline; user never sees Python.
- Native webview UI for inputs, progress, library browsing on desktop.
- BYOK stored in OS keychain (macOS Keychain, Windows Credential Manager).
- The Python pipeline becomes a library exposed via a localhost HTTP/IPC API
  that both the desktop UI and the existing `audio-learn` CLI call into.

### Mobile audio (commute mode)

- Desktop app publishes generated MP3s + a personal RSS feed to user-owned
  object storage (Cloudflare R2 recommended: 10GB free, S3-compatible, public
  buckets, podcast-friendly URLs).
- User subscribes to their personal RSS in Apple Podcasts / Overcast / Pocket
  Casts / Spotify — once. New episodes appear automatically.
- All the things a podcast app does well (offline download, background play,
  lock-screen controls, AirPods scrub, CarPlay, speed, sleep timer) come for
  free.
- This flips the current spec's "no RSS feed" rule. It was reasonable under
  the Syncthing-sync assumption; it's the wrong call once mobile-first
  listening is the use case.

### Mobile interactive (sit-down mode)

- A small static PWA, hosted free on GitHub Pages / Cloudflare Pages by the
  project. No backend, no per-user state on our side — just a static site
  that reads from the user's storage.
- Renders the existing HTML player with audio↔slide sync.
- Same PWA doubles as the demo page on the project landing site (pre-loaded
  with one example bucket).
- Add-to-home-screen on phone; works on desktop too.

### Storage / credentials

- Start by supporting **one** provider well: Cloudflare R2. Onboarding is a
  guided 90-second walkthrough (create account, create bucket, generate
  token, paste into desktop app).
- Add B2, S3, others later if there's demand.
- BYOK + bucket credentials live on user devices only. The PWA's credentials
  are pasted on the phone (or paired from desktop via QR code) and stored in
  local storage.

## Distribution / hosting commitments

What we host:

- The project landing site + the static PWA (free, zero-maintenance, no
  per-user data).
- Pre-rendered demo episodes for the landing page.

What we **do not** host:

- The generator. It runs on the user's desktop.
- User episodes, transcripts, keys, or accounts.
- Any API proxying. BYOK = the user's API calls go directly from their
  machine to Claude / Gemini / etc.

## Explicit non-goals (for v1 of the app expansion)

- Native iOS / Android apps. PWA + standard podcast apps cover it.
- Real-time tunnel access to a home server (Tailscale etc.). Out of scope
  for non-technical users.
- Multi-user / shared libraries / collaboration. Personal-scale only.
- Spaced repetition, flashcards, quizzes, progress tracking. BeFreed already
  does this; not our differentiator. Could be added later.
- Hosted "try-it-live" generation. Static demo only.
- Competing with NotebookLM on audio quality or BeFreed on personalized
  learning paths.

## What flips in the current spec

If we go this direction, these assumptions in the current design need to be
revisited:

- "No HTTP server" → desktop app has a local FastAPI layer wrapping the
  pipeline. (Still no remote server; still no external HTTP.)
- "No RSS feed" → optional RSS generation + publish step.
- Output is "files in `OUTPUT_DIR`" → output is files locally, plus an
  optional publish step that uploads + updates `feed.xml`.
- HTML player needs to be **self-contained** (all assets inlined or
  co-located, no broken relative paths when served from a bucket,
  CORS-safe). Worth designing for from Phase 1 to avoid a rewrite later.

## Phasing (rough)

Order matters; each phase is independently valuable.

1. **Phase 1 (current)**: CLI + library + interactive HTML player. Ship as
   planned. Ensure player is self-contained.
2. **Phase 2a**: RSS feed generation + publish-to-R2 step. CLI flag is fine
   for now; mobile commute experience unlocked even without a desktop app.
3. **Phase 2b**: Tauri desktop app shell around the pipeline. Non-developer
   install path.
4. **Phase 2c**: Static PWA for the interactive sit-down mobile experience.
   Also serves as the project demo page.
5. **Phase 3+**: Anything else (flashcards, more storage backends, etc.) is
   optional and gets evaluated against "does this actually serve me / people
   like me, or am I drifting into BeFreed's territory?"

## Competitive landscape

Snapshot from a web search done during the discussion (May 2026):

**Hosted commercial (crowded, well-funded):**
- **NotebookLM** (Google): two-host audio overview from documents, free.
- **BeFreed**: 500k+ users, iOS + Android, $12.99/mo or $179 lifetime,
  personalized learning paths, host voice customization, spaced repetition.
- Studley, Studygenie, Poddle, Scholarly, Turbo AI, Quizgecko, Wondercraft —
  variations on the same theme, mostly subscription mobile apps.

**OSS NotebookLM clones (also crowded):**
- **Open Notebook** (`lfnovo/open-notebook`): most mature; 18+ providers,
  1-4 speakers, REST API, citations. Docker self-host.
- **Podcastfy** (`souzatharsis/podcastfy`): Python package, 100+ LLMs,
  multilingual, multi-modal inputs.
- **open-notebooklm** (`gabrielchua/open-notebooklm`): PDF → podcast.
- **InsightsLM**: React + Supabase + N8N stack.
- **NotebookMLX**: Apple Silicon port.

**Gaps in current OSS offerings:**
- All require Docker / Python / dev-audience setup.
- None ship a desktop installer for non-developers.
- None integrate with standard podcast apps via RSS for the
  commute-on-mobile use case.
- None do the audio↔slide synced HTML player as a differentiating
  experience.

## Open questions to revisit

These were raised in the discussion but not resolved:

1. **R2 onboarding cliff.** A guided walkthrough lowers the "create a
   Cloudflare account" friction, but doesn't eliminate it. Worth
   prototyping the onboarding flow on a real non-technical person before
   committing to BYO-storage as the model.
2. **Code-signing budget.** Mac notarization ($99/yr Apple Developer) and
   Windows code-signing certs are real ongoing costs for an OSS project.
   Unsigned binaries kill non-technical adoption. Worth deciding if we're
   OK paying.
3. **Install-size ceiling.** Bundling Python + ffmpeg + player runtime can
   hit 200–400MB. Probably fine, but worth knowing the limit.
4. **iOS PWA limitations** for the interactive sit-down mode. Background
   audio is iffy; might be acceptable since serious listening goes through
   the podcast app via RSS anyway.
5. **Should the player become a proper offline-cacheable PWA from day 1,
   or stay a one-off HTML file?** Affects Phase 1 design choices.

## What this doc is not

Not a spec. Not a commitment. Not a roadmap. A starting point to pick up
from when the maintainer is ready to think about Phase 2.

The Phase 1 plan in `docs/superpowers/plans/` is unaffected — finish that
first, then decide whether any of this is worth pursuing.
