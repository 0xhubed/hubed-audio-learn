# Single-Narrator Explainer (OSS / Kokoro-over-HTTP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `audio-learn explain` mode that produces a single-narrator audio explainer (MP3 + synced-slide HTML) from a topic, voiced by an open-source Kokoro TTS server running on the DGX Spark, reachable over HTTP.

**Architecture:** Reuse the existing `research → outline` stages unchanged. Replace the two-host `script → tts` stages with a single-narrator `explainer → explainer_tts` pair. The explainer script is a flat list of short narration *segments* (no speakers); each segment optionally carries a `slide_marker`. TTS synthesizes **one segment at a time** against an OpenAI-compatible `/v1/audio/speech` endpoint, concatenates the clips locally, and records each segment's exact start offset — eliminating the podcast path's fragile silence-detection timing (review finding #6). `html_render` and `package` are generalized to accept either turns or segments. A final optional task adds an OpenAI-compatible LLM provider so the *script-writing* step can also run on an OSS model on the DGX.

**Tech Stack:** Python 3.11+, pydantic v2, httpx (HTTP client for the TTS/LLM endpoints), pydub (audio concat + MP3 encode), Jinja2 (player), Kokoro-FastAPI (the DGX-side server exposing `/v1/audio/speech`, e.g. `remsky/Kokoro-FastAPI`).

**Deployment assumption:** The `audio-learn` CLI runs on the laptop. A Kokoro server runs on the DGX exposing the OpenAI-compatible TTS route at `KOKORO_URL` (default `http://localhost:8880`). The provider is HTTP-only and needs no CUDA/heavy deps on the laptop.

---

## File structure

| File | Responsibility | New/Modified |
| --- | --- | --- |
| `src/hubed_audio_learn/schemas/explainer.py` | `Explainer` / `ExplainerSegment` models | New |
| `src/hubed_audio_learn/schemas/__init__.py` | Export the new models | Modify |
| `src/hubed_audio_learn/prompts/explainer_system.txt` | System prompt for the explainer stage | New |
| `src/hubed_audio_learn/pipeline/explainer.py` | `run_explainer`: outline.json → explainer.json | New |
| `src/hubed_audio_learn/config.py` | Kokoro + narrator config fields | Modify |
| `src/hubed_audio_learn/providers/tts/kokoro.py` | `KokoroHTTPProvider.synthesize_segments` | New |
| `src/hubed_audio_learn/providers/tts/__init__.py` | `load_explainer_tts_provider` loader | Modify |
| `src/hubed_audio_learn/pipeline/explainer_tts.py` | `run_explainer_tts`: explainer.json → episode.mp3 + timing.json | New |
| `src/hubed_audio_learn/pipeline/html_render.py` | Generalize helpers; add `run_html_render_explainer` | Modify |
| `src/hubed_audio_learn/pipeline/package.py` | Explainer transcript + manifest (detect content type) | Modify |
| `src/hubed_audio_learn/cli.py` | `explain` subcommand | Modify |
| `src/hubed_audio_learn/providers/llm/openai_compat.py` | OpenAI-compatible LLM provider | New (Task 9) |
| `src/hubed_audio_learn/providers/llm/__init__.py` | Register OSS LLM in loader | Modify (Task 9) |
| `pyproject.toml` | Add `httpx` dependency | Modify |
| `.env.example`, `README.md` | Document the explainer mode + Kokoro server | Modify (Task 10) |
| `tests/fixtures/sample_explainer.json` | Shared explainer fixture | New |

---

## Task 1: Explainer schema

**Files:**
- Create: `src/hubed_audio_learn/schemas/explainer.py`
- Modify: `src/hubed_audio_learn/schemas/__init__.py`
- Create: `tests/fixtures/sample_explainer.json`
- Test: `tests/test_schemas.py` (append)

- [ ] **Step 1: Write the failing test** — append to `tests/test_schemas.py`:

```python
def test_explainer_validates_and_forbids_extra_fields():
    from pydantic import ValidationError
    from hubed_audio_learn.schemas import Explainer

    data = {
        "outline_ref": "outline.json",
        "narrator_name": "Sam",
        "segments": [
            {"text": "Kalman filters estimate state from noisy measurements.",
             "section_ref": "intro", "slide_marker": None},
            {"text": "Here is the prediction step.",
             "section_ref": "prediction",
             "slide_marker": {"figure_id": "fig-predict", "cue": "soft"}},
        ],
    }
    exp = Explainer.model_validate(data)
    assert len(exp.segments) == 2
    assert exp.segments[1].slide_marker.figure_id == "fig-predict"

    with pytest.raises(ValidationError):
        Explainer.model_validate({**data, "unexpected": 1})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schemas.py::test_explainer_validates_and_forbids_extra_fields -v`
Expected: FAIL with `ImportError: cannot import name 'Explainer'`.

- [ ] **Step 3: Create `src/hubed_audio_learn/schemas/explainer.py`**

```python
"""Schema for explainer.json — single-narrator audio explainer script."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from hubed_audio_learn.schemas.script import SlideMarker


class ExplainerSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    section_ref: str
    slide_marker: SlideMarker | None = None


class Explainer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outline_ref: str
    narrator_name: str
    segments: list[ExplainerSegment]
```

- [ ] **Step 4: Export from `src/hubed_audio_learn/schemas/__init__.py`**

Add an import and extend `__all__`:

```python
from hubed_audio_learn.schemas.explainer import Explainer, ExplainerSegment
```

Add `"Explainer"` and `"ExplainerSegment"` to the module's `__all__` list.

- [ ] **Step 5: Create `tests/fixtures/sample_explainer.json`**

```json
{
  "outline_ref": "outline.json",
  "narrator_name": "Sam",
  "segments": [
    {"text": "Today we look at Kalman filters and why they matter.", "section_ref": "intro", "slide_marker": null},
    {"text": "Picture a car estimating its position from GPS and a wheel encoder.", "section_ref": "intro", "slide_marker": {"figure_id": "fig-scenario-car", "cue": "soft"}},
    {"text": "The prediction step propagates the state estimate forward in time.", "section_ref": "prediction", "slide_marker": {"figure_id": "fig-predict", "cue": "soft"}}
  ]
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_schemas.py::test_explainer_validates_and_forbids_extra_fields -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hubed_audio_learn/schemas/explainer.py src/hubed_audio_learn/schemas/__init__.py tests/fixtures/sample_explainer.json tests/test_schemas.py
git commit -m "feat: explainer schema for single-narrator scripts"
```

---

## Task 2: Explainer stage (outline.json → explainer.json)

**Files:**
- Create: `src/hubed_audio_learn/prompts/explainer_system.txt`
- Create: `src/hubed_audio_learn/pipeline/explainer.py`
- Test: `tests/test_explainer.py`

- [ ] **Step 1: Create `src/hubed_audio_learn/prompts/explainer_system.txt`**

```
You convert an outline into a single-narrator audio explainer script.

A single narrator explains the topic clearly and precisely for the assumed
audience. Reference figures by `figure_id` at the moment they should appear on
screen via the `slide_marker` field. Keep each segment to 2-4 sentences so the
slide changes at natural points. Avoid stage directions and audio cues.

Emit ONLY a JSON object matching this schema (no markdown, no commentary):

{
  "outline_ref": "outline.json",
  "narrator_name": <string>,
  "segments": [
    {
      "text": <string, 2-4 sentences>,
      "section_ref": <section.id from the outline>,
      "slide_marker": null | {"figure_id": <figure.id>, "cue": "soft"|"hard"}
    }
  ]
}

Word-count targets:
- short:  ~1000 words total
- medium: ~2400 words total
- long:   ~5000 words total

Open with a one-sentence framing of why the topic matters. Close with a concise
recap of the key takeaways. Every figure in the outline must be cued at least
once. Prefer precision over chattiness; define jargon the first time it appears.
```

- [ ] **Step 2: Write the failing test** — `tests/test_explainer.py`:

```python
"""Explainer stage unit tests with a fake LLM."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hubed_audio_learn.pipeline.explainer import run_explainer


class _FakeLLM:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def generate(self, prompt, *, allowed_tools=None, timeout_seconds=600):
        self.calls.append(prompt)
        return self._replies.pop(0)


_VALID = json.dumps({
    "outline_ref": "outline.json",
    "narrator_name": "Sam",
    "segments": [
        {"text": "Intro sentence.", "section_ref": "intro", "slide_marker": None},
    ],
})


def _seed_outline(work: Path, load_fixture):
    (work / "outline.json").write_text(json.dumps(load_fixture("sample_outline.json")))


def test_run_explainer_writes_valid_json(tmp_work_dir: Path, load_fixture):
    _seed_outline(tmp_work_dir, load_fixture)
    llm = _FakeLLM([_VALID])
    out = run_explainer(work_dir=tmp_work_dir, target_length="medium",
                        narrator_name="Sam", llm=llm)
    assert out == tmp_work_dir / "explainer.json"
    data = json.loads(out.read_text())
    assert data["segments"][0]["section_ref"] == "intro"
    assert "target_length: medium" in llm.calls[0]


def test_run_explainer_retries_once_on_bad_json(tmp_work_dir: Path, load_fixture):
    _seed_outline(tmp_work_dir, load_fixture)
    llm = _FakeLLM(["not json", _VALID])
    run_explainer(work_dir=tmp_work_dir, target_length="short",
                  narrator_name="Sam", llm=llm)
    assert len(llm.calls) == 2
    assert "did not validate" in llm.calls[1]


def test_run_explainer_raises_after_two_failures(tmp_work_dir: Path, load_fixture):
    _seed_outline(tmp_work_dir, load_fixture)
    llm = _FakeLLM(["nope", "still nope"])
    with pytest.raises(RuntimeError, match="explainer stage failed"):
        run_explainer(work_dir=tmp_work_dir, target_length="short",
                      narrator_name="Sam", llm=llm)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_explainer.py -v`
Expected: FAIL with `ModuleNotFoundError: ... pipeline.explainer`.

- [ ] **Step 4: Create `src/hubed_audio_learn/pipeline/explainer.py`**

```python
"""Stage 3 (explainer path) — convert outline.json into explainer.json via one LLM call."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from hubed_audio_learn.providers.llm.base import LLMProvider
from hubed_audio_learn.schemas import Explainer


def _load_system_prompt() -> str:
    return resources.files("hubed_audio_learn.prompts").joinpath("explainer_system.txt").read_text(encoding="utf-8")


def _build_prompt(
    outline_json: str,
    target_length: str,
    narrator_name: str,
    retry_error: str | None = None,
) -> str:
    parts = [
        _load_system_prompt(),
        "",
        f"target_length: {target_length}",
        f"narrator_name: {narrator_name}",
        "",
        "Outline:",
        outline_json,
    ]
    if retry_error:
        parts.extend(["", "Your previous response did not validate:", retry_error, "Return ONLY the corrected JSON."])
    return "\n".join(parts)


def run_explainer(
    *,
    work_dir: Path,
    target_length: str,
    narrator_name: str,
    llm: LLMProvider,
    timeout_seconds: int = 600,
) -> Path:
    outline_path = work_dir / "outline.json"
    if not outline_path.exists():
        raise FileNotFoundError(f"outline.json not found in {work_dir}")
    outline_json = outline_path.read_text(encoding="utf-8")
    out_path = work_dir / "explainer.json"

    last_error: str | None = None
    for attempt in range(2):
        prompt = _build_prompt(
            outline_json,
            target_length,
            narrator_name,
            retry_error=last_error if attempt == 1 else None,
        )
        raw = llm.generate(prompt, allowed_tools=None, timeout_seconds=timeout_seconds)
        try:
            data = json.loads(raw)
            explainer = Explainer.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            continue
        out_path.write_text(explainer.model_dump_json(indent=2), encoding="utf-8")
        return out_path

    raise RuntimeError(f"explainer stage failed after 2 attempts: {last_error}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_explainer.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/hubed_audio_learn/prompts/explainer_system.txt src/hubed_audio_learn/pipeline/explainer.py tests/test_explainer.py
git commit -m "feat: explainer stage with single-narrator script generation"
```

---

## Task 3: Config fields for Kokoro + narrator

**Files:**
- Modify: `src/hubed_audio_learn/config.py`
- Modify: `pyproject.toml`
- Test: `tests/test_config.py` (append)

- [ ] **Step 1: Write the failing test** — append to `tests/test_config.py`:

```python
def test_load_config_reads_kokoro_and_narrator(monkeypatch):
    from hubed_audio_learn.config import load_config
    monkeypatch.setenv("KOKORO_URL", "http://dgx.local:8880")
    monkeypatch.setenv("KOKORO_VOICE", "am_michael")
    monkeypatch.setenv("NARRATOR_NAME", "Nova")
    cfg = load_config(env_file=None)
    assert cfg.kokoro_url == "http://dgx.local:8880"
    assert cfg.kokoro_voice == "am_michael"
    assert cfg.narrator_name == "Nova"


def test_kokoro_defaults(monkeypatch):
    from hubed_audio_learn.config import load_config
    for k in ("KOKORO_URL", "KOKORO_VOICE", "KOKORO_MODEL", "NARRATOR_NAME"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config(env_file=None)
    assert cfg.kokoro_url == "http://localhost:8880"
    assert cfg.kokoro_voice == "af_heart"
    assert cfg.kokoro_model == "kokoro"
    assert cfg.narrator_name == "Sam"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -k "kokoro or narrator" -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'kokoro_url'`.

- [ ] **Step 3: Add fields to the `Config` model** in `src/hubed_audio_learn/config.py`, after the `gemini_tts_model` line:

```python
    kokoro_url: str = "http://localhost:8880"
    kokoro_voice: str = "af_heart"
    kokoro_model: str = "kokoro"
    narrator_name: str = "Sam"
```

- [ ] **Step 4: Populate them in `load_config`**, inside the `return Config(...)` call (after the `gemini_tts_model=` line):

```python
        kokoro_url=os.environ.get("KOKORO_URL", "http://localhost:8880"),
        kokoro_voice=os.environ.get("KOKORO_VOICE", "af_heart"),
        kokoro_model=os.environ.get("KOKORO_MODEL", "kokoro"),
        narrator_name=os.environ.get("NARRATOR_NAME", "Sam"),
```

- [ ] **Step 5: Add `httpx` to dependencies** in `pyproject.toml` `dependencies` list:

```toml
    "httpx>=0.27",
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: all config tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/hubed_audio_learn/config.py pyproject.toml tests/test_config.py
git commit -m "feat: config fields for Kokoro TTS endpoint and narrator"
```

---

## Task 4: Kokoro HTTP TTS provider

**Files:**
- Create: `src/hubed_audio_learn/providers/tts/kokoro.py`
- Test: `tests/test_kokoro_provider.py`

The provider POSTs each segment to the OpenAI-compatible `/v1/audio/speech` route, receives WAV bytes, decodes with pydub to measure exact duration, concatenates, and exports one MP3. Returns `(mp3_bytes, start_offsets_seconds)`.

- [ ] **Step 1: Write the failing test** — `tests/test_kokoro_provider.py`:

```python
"""Kokoro HTTP provider tests with a mocked httpx client and synthetic WAV clips."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from hubed_audio_learn.providers.tts.kokoro import KokoroHTTPProvider


def _wav_bytes(ms: int) -> bytes:
    seg = Sine(220).to_audio_segment(duration=ms)
    buf = io.BytesIO()
    seg.export(buf, format="wav")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.status_code = 200

    def raise_for_status(self):
        pass


def test_synthesize_segments_returns_offsets_from_clip_durations():
    provider = KokoroHTTPProvider(base_url="http://dgx:8880", voice="af_heart", model="kokoro")
    # 1000ms then 500ms clips -> offsets 0.0, 1.0
    responses = [_FakeResponse(_wav_bytes(1000)), _FakeResponse(_wav_bytes(500))]
    fake_client = MagicMock()
    fake_client.post.side_effect = responses
    fake_client.__enter__.return_value = fake_client
    fake_client.__exit__.return_value = False

    with patch("hubed_audio_learn.providers.tts.kokoro.httpx.Client", return_value=fake_client):
        mp3, offsets = provider.synthesize_segments(["one", "two"])

    assert mp3[:3] == b"ID3" or len(mp3) > 0  # an MP3 payload came back
    assert offsets[0] == 0.0
    assert offsets[1] == pytest.approx(1.0, abs=0.05)
    # the request used the OpenAI-compatible shape
    sent = fake_client.post.call_args_list[0]
    assert sent.args[0].endswith("/v1/audio/speech")
    assert sent.kwargs["json"]["input"] == "one"
    assert sent.kwargs["json"]["voice"] == "af_heart"


def test_synthesize_segments_empty_raises():
    provider = KokoroHTTPProvider(base_url="http://dgx:8880", voice="af_heart", model="kokoro")
    with pytest.raises(ValueError, match="no segments"):
        provider.synthesize_segments([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kokoro_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: ... providers.tts.kokoro`.

- [ ] **Step 3: Create `src/hubed_audio_learn/providers/tts/kokoro.py`**

```python
"""Kokoro single-speaker TTS over an OpenAI-compatible HTTP endpoint.

The CLI runs on the laptop and calls a Kokoro server (e.g. Kokoro-FastAPI) on the
DGX Spark via POST {base_url}/v1/audio/speech. We synthesize one segment at a time
so each segment's start offset is exact (the cumulative duration of prior clips),
which removes any need for silence-detection timing.
"""
from __future__ import annotations

import io
from typing import Sequence

import httpx
from pydub import AudioSegment

_SPEECH_PATH = "/v1/audio/speech"


class KokoroHTTPProvider:
    name = "kokoro"
    supported_languages = ["en"]

    def __init__(self, base_url: str, voice: str, model: str = "kokoro", timeout_seconds: int = 300):
        self.base_url = base_url.rstrip("/")
        self.voice = voice
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _synthesize_one(self, client: httpx.Client, text: str) -> AudioSegment:
        resp = client.post(
            f"{self.base_url}{_SPEECH_PATH}",
            json={
                "model": self.model,
                "input": text,
                "voice": self.voice,
                "response_format": "wav",
            },
        )
        resp.raise_for_status()
        return AudioSegment.from_file(io.BytesIO(resp.content), format="wav")

    def synthesize_segments(self, texts: Sequence[str]) -> tuple[bytes, list[float]]:
        """Render each text segment, concatenate, return (mp3_bytes, start_offsets_seconds)."""
        if not texts:
            raise ValueError("synthesize_segments received no segments")

        combined = AudioSegment.empty()
        offsets: list[float] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for text in texts:
                offsets.append(round(len(combined) / 1000.0, 3))
                combined += self._synthesize_one(client, text)

        buf = io.BytesIO()
        combined.export(buf, format="mp3", bitrate="96k")
        return buf.getvalue(), offsets
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kokoro_provider.py -v`
Expected: 2 passed. (Requires `ffmpeg` on PATH for pydub WAV/MP3 handling.)

- [ ] **Step 5: Commit**

```bash
git add src/hubed_audio_learn/providers/tts/kokoro.py tests/test_kokoro_provider.py
git commit -m "feat: Kokoro HTTP TTS provider with per-segment exact timing"
```

---

## Task 5: Explainer TTS pipeline stage + loader

**Files:**
- Create: `src/hubed_audio_learn/pipeline/explainer_tts.py`
- Modify: `src/hubed_audio_learn/providers/tts/__init__.py`
- Test: `tests/test_explainer_tts.py`

- [ ] **Step 1: Add the loader** to `src/hubed_audio_learn/providers/tts/__init__.py`. Extend `__all__` with `"load_explainer_tts_provider"` and append:

```python
def load_explainer_tts_provider(name: str, *, base_url: str, voice: str,
                                model: str = "kokoro", timeout_seconds: int = 300):
    if name == "kokoro":
        from hubed_audio_learn.providers.tts.kokoro import KokoroHTTPProvider
        return KokoroHTTPProvider(base_url=base_url, voice=voice, model=model,
                                  timeout_seconds=timeout_seconds)
    raise ValueError(f"Unknown explainer TTS provider: {name!r}. Supported: 'kokoro'.")
```

- [ ] **Step 2: Write the failing test** — `tests/test_explainer_tts.py`:

```python
"""Explainer TTS stage test with a fake provider."""
from __future__ import annotations

import json
from pathlib import Path

from hubed_audio_learn.pipeline.explainer_tts import run_explainer_tts


class _FakeTTS:
    def __init__(self):
        self.received = None

    def synthesize_segments(self, texts):
        self.received = list(texts)
        return b"FAKEMP3", [0.0, 1.5, 3.0]


def _seed_explainer(work: Path, load_fixture):
    (work / "explainer.json").write_text(json.dumps(load_fixture("sample_explainer.json")))


def test_run_explainer_tts_writes_mp3_and_timing(tmp_work_dir: Path, load_fixture):
    _seed_explainer(tmp_work_dir, load_fixture)
    tts = _FakeTTS()
    run_explainer_tts(work_dir=tmp_work_dir, tts=tts)

    assert tts.received[0].startswith("Today we look")
    assert (tmp_work_dir / "episode.mp3").read_bytes() == b"FAKEMP3"
    timing = json.loads((tmp_work_dir / "timing.json").read_text())
    assert [t["index"] for t in timing["turns"]] == [0, 1, 2]
    assert timing["turns"][1]["start_seconds"] == 1.5
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_explainer_tts.py -v`
Expected: FAIL with `ModuleNotFoundError: ... pipeline.explainer_tts`.

- [ ] **Step 4: Create `src/hubed_audio_learn/pipeline/explainer_tts.py`**

```python
"""Stage 4 (explainer path) — synthesize explainer.json into episode.mp3 + timing.json.

`timing.json` reuses the podcast Timing schema: one entry per segment, where the
entry index matches the segment index. Offsets are exact (per-segment synthesis),
so no silence detection is involved.
"""
from __future__ import annotations

from pathlib import Path

from hubed_audio_learn.schemas import Explainer, Timing, TurnTiming


def run_explainer_tts(*, work_dir: Path, tts) -> Path:
    explainer = Explainer.model_validate_json((work_dir / "explainer.json").read_text(encoding="utf-8"))
    texts = [seg.text for seg in explainer.segments]

    mp3_bytes, offsets = tts.synthesize_segments(texts)

    (work_dir / "episode.mp3").write_bytes(mp3_bytes)
    timing = Timing(turns=[TurnTiming(index=i, start_seconds=s) for i, s in enumerate(offsets)])
    (work_dir / "timing.json").write_text(timing.model_dump_json(indent=2), encoding="utf-8")
    return work_dir / "episode.mp3"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_explainer_tts.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hubed_audio_learn/pipeline/explainer_tts.py src/hubed_audio_learn/providers/tts/__init__.py tests/test_explainer_tts.py
git commit -m "feat: explainer TTS stage and Kokoro loader"
```

---

## Task 6: HTML render for the explainer (generalize helpers)

**Files:**
- Modify: `src/hubed_audio_learn/pipeline/html_render.py`
- Test: `tests/test_html_render.py` (append)

The three helper functions currently take a `Script` and read `.turns`. Both turns and segments expose `.slide_marker`, so generalize the helpers to take a list of "marked units" and add an explainer entry point. The existing `run_html_render` keeps working by passing `script.turns`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_html_render.py`:

```python
def test_run_html_render_explainer_emits_active_slides(tmp_work_dir, load_fixture):
    import json
    from hubed_audio_learn.pipeline.html_render import run_html_render_explainer

    (tmp_work_dir / "outline.json").write_text(json.dumps(load_fixture("sample_outline.json")))
    (tmp_work_dir / "explainer.json").write_text(json.dumps(load_fixture("sample_explainer.json")))
    (tmp_work_dir / "timing.json").write_text(json.dumps({
        "turns": [{"index": 0, "start_seconds": 0.0},
                  {"index": 1, "start_seconds": 2.0},
                  {"index": 2, "start_seconds": 5.0}]
    }))

    out = run_html_render_explainer(work_dir=tmp_work_dir, mp3_filename="episode.mp3")
    html = out.read_text()
    assert 'src="episode.mp3"' in html
    assert 'data-figure-id="fig-scenario-car"' in html
    assert 'data-figure-id="fig-predict"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_html_render.py::test_run_html_render_explainer_emits_active_slides -v`
Expected: FAIL with `ImportError: cannot import name 'run_html_render_explainer'`.

- [ ] **Step 3: Generalize the helpers and add the explainer entry point** in `src/hubed_audio_learn/pipeline/html_render.py`.

Change the three helper signatures to take `units` (a list with `.slide_marker`) instead of `script`, and update `run_html_render` to pass `script.turns`. The bodies are unchanged except they iterate `units` instead of `script.turns`:

```python
def _figure_first_starts(units, timing: Timing) -> dict[str, float]:
    start_by_index = {t.index: t.start_seconds for t in timing.turns}
    firsts: dict[str, float] = {}
    for i, unit in enumerate(units):
        if unit.slide_marker and unit.slide_marker.figure_id not in firsts:
            firsts[unit.slide_marker.figure_id] = start_by_index.get(i, 0.0)
    return firsts


def _markers_map(units) -> dict[str, str]:
    result: dict[str, str] = {}
    current: str | None = None
    for i, unit in enumerate(units):
        if unit.slide_marker:
            current = unit.slide_marker.figure_id
        if current is not None:
            result[str(i)] = current
    return result


def _ordered_figures(outline: Outline, units, firsts: dict[str, float]) -> list[dict]:
    fig_lookup = {f.id: f for section in outline.sections for f in section.figures}
    seen: list[str] = []
    for unit in units:
        if unit.slide_marker and unit.slide_marker.figure_id not in seen:
            seen.append(unit.slide_marker.figure_id)
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
```

Update the existing `run_html_render` body to call the helpers with `script.turns`:

```python
    firsts = _figure_first_starts(script.turns, timing)
    figures = _ordered_figures(outline, script.turns, firsts)
    markers = _markers_map(script.turns)
```

Extend the existing schemas import near the top (it currently reads `from hubed_audio_learn.schemas import Outline, Script, Timing`) to add `Explainer`:

```python
from hubed_audio_learn.schemas import Explainer, Outline, Script, Timing
```

Add the explainer entry point at the end of the file:

```python
def run_html_render_explainer(*, work_dir: Path, mp3_filename: str) -> Path:
    outline = Outline.model_validate_json((work_dir / "outline.json").read_text(encoding="utf-8"))
    explainer = Explainer.model_validate_json((work_dir / "explainer.json").read_text(encoding="utf-8"))
    timing = Timing.model_validate_json((work_dir / "timing.json").read_text(encoding="utf-8"))

    firsts = _figure_first_starts(explainer.segments, timing)
    figures = _ordered_figures(outline, explainer.segments, firsts)
    markers = _markers_map(explainer.segments)

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
```

- [ ] **Step 4: Run the full html_render test file to verify nothing regressed**

Run: `python -m pytest tests/test_html_render.py -v`
Expected: existing podcast tests still pass + the new explainer test passes.

- [ ] **Step 5: Commit**

```bash
git add src/hubed_audio_learn/pipeline/html_render.py tests/test_html_render.py
git commit -m "feat: HTML render for explainer; generalize slide helpers"
```

---

## Task 7: Package the explainer (transcript + manifest)

**Files:**
- Modify: `src/hubed_audio_learn/pipeline/package.py`
- Test: `tests/test_package.py` (append)

`run_package` currently assumes a `script.json` with two hosts. Make it detect content type: if `explainer.json` exists, build a speaker-less transcript and a manifest keyed off segments; otherwise keep the existing podcast behavior unchanged.

- [ ] **Step 1: Write the failing test** — append to `tests/test_package.py`:

```python
def _seed_explainer_work_dir(work: Path, load_fixture) -> None:
    (work / "outline.json").write_text(json.dumps(load_fixture("sample_outline.json")))
    (work / "explainer.json").write_text(json.dumps(load_fixture("sample_explainer.json")))
    (work / "timing.json").write_text(json.dumps({
        "turns": [{"index": 0, "start_seconds": 0.0},
                  {"index": 1, "start_seconds": 3.0},
                  {"index": 2, "start_seconds": 8.0}]
    }))
    (work / "episode.mp3").write_bytes(b"ID3\x00MP3")
    (work / "episode.html").write_text('<audio src="episode.mp3"></audio>')


def test_run_package_explainer_transcript_has_no_speaker_names(tmp_work_dir: Path, tmp_output_dir: Path, load_fixture):
    _seed_explainer_work_dir(tmp_work_dir, load_fixture)
    run_package(
        work_dir=tmp_work_dir,
        output_dir=tmp_output_dir,
        topic="Kalman filters",
        date_str="2026-05-28",
        providers={"llm": "claude", "tts": "kokoro"},
        stage_durations={},
    )
    transcript = (tmp_output_dir / "2026-05-28-kalman-filters.transcript.md").read_text()
    assert "[00:00]" in transcript
    assert "Today we look" in transcript
    assert "Alex:" not in transcript and "Sam:" not in transcript

    manifest = json.loads((tmp_output_dir / "2026-05-28-kalman-filters.manifest.json").read_text())
    assert manifest["segment_count"] == 3
    assert "fig-predict" in [f["id"] for f in manifest["figures_referenced"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_package.py::test_run_package_explainer_transcript_has_no_speaker_names -v`
Expected: FAIL — `run_package` still reads `script.json` and raises `FileNotFoundError`, or the manifest lacks `segment_count`.

- [ ] **Step 3: Add explainer helpers and a content branch to `package.py`.**

Extend the existing schemas import (it currently reads `from hubed_audio_learn.schemas import Outline, Script, Timing`) to add `Explainer`:

```python
from hubed_audio_learn.schemas import Explainer, Outline, Script, Timing
```

Add a speaker-less transcript builder next to `_build_transcript`:

```python
def _build_explainer_transcript(explainer: Explainer, timing: Timing) -> str:
    start_by_index = {t.index: t.start_seconds for t in timing.turns}
    lines: list[str] = []
    for i, seg in enumerate(explainer.segments):
        ts = _format_timestamp(start_by_index.get(i, 0.0))
        lines.append(f"[{ts}] {seg.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

Add an explainer manifest builder next to `_build_manifest`:

```python
def _build_explainer_manifest(
    *,
    topic: str,
    date_str: str,
    slug: str,
    providers: dict[str, Any],
    stage_durations: dict[str, float],
    outline: Outline,
    explainer: Explainer,
    timing: Timing,
    mp3_bytes_size: int,
) -> dict[str, Any]:
    figures_referenced = []
    seen: set[str] = set()
    for seg in explainer.segments:
        if seg.slide_marker and seg.slide_marker.figure_id not in seen:
            seen.add(seg.slide_marker.figure_id)
            figures_referenced.append({"id": seg.slide_marker.figure_id})

    return {
        "schema_version": 1,
        "format": "explainer",
        "topic": topic,
        "slug": slug,
        "date": date_str,
        "providers": providers,
        "stage_durations_seconds": stage_durations,
        "segment_count": len(explainer.segments),
        "tts_character_count": sum(len(s.text) for s in explainer.segments),
        "last_segment_start_seconds": (timing.turns[-1].start_seconds if timing.turns else 0.0),
        "mp3_bytes": mp3_bytes_size,
        "sources": [s.model_dump() for s in outline.sources_used],
        "figures_referenced": figures_referenced,
        "target_length": outline.target_length,
    }
```

In `run_package`, after computing `base`/paths and loading `outline`/`timing`, branch on whether `explainer.json` exists. Replace the block that currently loads `script` and builds the transcript/manifest with:

```python
    outline = Outline.model_validate_json((work_dir / "outline.json").read_text(encoding="utf-8"))
    timing = Timing.model_validate_json((work_dir / "timing.json").read_text(encoding="utf-8"))

    is_explainer = (work_dir / "explainer.json").exists()
    if is_explainer:
        explainer = Explainer.model_validate_json((work_dir / "explainer.json").read_text(encoding="utf-8"))
        transcript_text = _build_explainer_transcript(explainer, timing)
    else:
        script = Script.model_validate_json((work_dir / "script.json").read_text(encoding="utf-8"))
        transcript_text = _build_transcript(script, timing)
```

Keep the file copies (`episode.mp3`, `outline.json`) and the HTML `src` rewrite as-is, then write the transcript from `transcript_text`:

```python
    final_transcript.write_text(transcript_text, encoding="utf-8")
```

Replace the manifest construction with the branch:

```python
    if is_explainer:
        manifest = _build_explainer_manifest(
            topic=topic, date_str=date_str, slug=slug, providers=providers,
            stage_durations=stage_durations, outline=outline, explainer=explainer,
            timing=timing, mp3_bytes_size=final_mp3.stat().st_size,
        )
    else:
        manifest = _build_manifest(
            topic=topic, date_str=date_str, slug=slug, providers=providers,
            stage_durations=stage_durations, outline=outline, script=script,
            timing=timing, mp3_bytes_size=final_mp3.stat().st_size,
        )
```

- [ ] **Step 4: Run the full package test file to verify nothing regressed**

Run: `python -m pytest tests/test_package.py -v`
Expected: existing podcast packaging tests still pass + the new explainer test passes.

- [ ] **Step 5: Commit**

```bash
git add src/hubed_audio_learn/pipeline/package.py tests/test_package.py
git commit -m "feat: package explainer episodes (speaker-less transcript + manifest)"
```

---

## Task 8: `explain` CLI subcommand

**Files:**
- Modify: `src/hubed_audio_learn/cli.py`
- Test: `tests/test_cli.py` (append)

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli.py`. Mirror the style of the existing CLI tests (they patch the pipeline stage functions). Patch the explainer pipeline functions and assert the parser dispatches `explain`:

```python
def test_explain_subcommand_runs_pipeline(tmp_path, monkeypatch):
    import hubed_audio_learn.cli as cli

    calls = []
    monkeypatch.setattr(cli, "load_config", lambda: cli.Config(
        gemini_api_key="", llm_provider="claude", tts_provider="kokoro",
        output_dir=tmp_path / "out", work_dir=tmp_path / "work",
    ))
    monkeypatch.setattr(cli, "load_llm_provider", lambda *a, **k: object())
    monkeypatch.setattr(cli, "load_explainer_tts_provider", lambda *a, **k: object())
    monkeypatch.setattr(cli, "run_research", lambda **k: calls.append("research"))
    monkeypatch.setattr(cli, "run_outline", lambda **k: calls.append("outline"))
    monkeypatch.setattr(cli, "run_explainer", lambda **k: calls.append("explainer"))
    monkeypatch.setattr(cli, "run_explainer_tts", lambda **k: calls.append("explainer_tts"))
    monkeypatch.setattr(cli, "run_html_render_explainer", lambda **k: calls.append("html"))
    monkeypatch.setattr(cli, "run_package", lambda **k: (tmp_path / "out" / "m.json"))

    rc = cli.main(["explain", "Kalman", "filters", "--length", "s"])
    assert rc == 0
    assert calls == ["research", "outline", "explainer", "explainer_tts", "html"]
```

> Note: confirm the exact monkeypatch targets match the import style already used in `tests/test_cli.py` for the `podcast` test; adjust attribute names if that test patches differently.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_explain_subcommand_runs_pipeline -v`
Expected: FAIL — `explain` is not a valid subcommand (argparse `SystemExit`).

- [ ] **Step 3: Wire the subcommand** in `src/hubed_audio_learn/cli.py`.

Add imports near the existing pipeline imports:

```python
from hubed_audio_learn.pipeline.explainer import run_explainer
from hubed_audio_learn.pipeline.explainer_tts import run_explainer_tts
from hubed_audio_learn.pipeline.html_render import run_html_render_explainer
from hubed_audio_learn.providers.tts import load_explainer_tts_provider
```

(Note: `run_html_render` is already imported; keep both imports.)

Add the command handler, modeled on `_cmd_podcast`:

```python
def _cmd_explain(args: argparse.Namespace) -> int:
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
    tts = load_explainer_tts_provider(
        cfg.tts_provider if cfg.tts_provider == "kokoro" else "kokoro",
        base_url=cfg.kokoro_url, voice=cfg.kokoro_voice, model=cfg.kokoro_model,
    )

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
    _timed("explainer", run_explainer,
           work_dir=work_dir, target_length=length, narrator_name=cfg.narrator_name,
           llm=llm, timeout_seconds=cfg.claude_timeout_seconds)
    _timed("explainer_tts", run_explainer_tts, work_dir=work_dir, tts=tts)
    _timed("html_render", run_html_render_explainer, work_dir=work_dir, mp3_filename="episode.mp3")

    manifest_path = _timed("package", run_package,
                           work_dir=work_dir, output_dir=cfg.output_dir,
                           topic=topic, date_str=date.today().isoformat(),
                           providers={"llm": cfg.llm_provider, "tts": "kokoro"},
                           stage_durations=durations)
    print(f"\nDone. Manifest: {manifest_path}")
    return 0
```

Register the subparser inside `_build_parser`, alongside `podcast`:

```python
    p_explain = sub.add_parser("explain", help="Generate a single-narrator audio explainer.")
    p_explain.add_argument("inputs", nargs="+", help="Topic words and/or paths to .pdf/.md/.txt/.rst files.")
    p_explain.add_argument("--length", choices=list(_LENGTH_MAP.keys()), default="medium")
    p_explain.add_argument("--prompt", default=None, help="Optional steering prompt for the LLM.")
    p_explain.set_defaults(func=_cmd_explain)
```

Also add `Config` to the cli imports if the test references `cli.Config` (it is already imported from `config` in `cli.py`).

- [ ] **Step 4: Run the full CLI test file**

Run: `python -m pytest tests/test_cli.py -v`
Expected: existing CLI tests still pass + the new explain test passes.

- [ ] **Step 5: Commit**

```bash
git add src/hubed_audio_learn/cli.py tests/test_cli.py
git commit -m "feat: 'explain' CLI subcommand for single-narrator explainer"
```

---

## Task 9 (optional, independent): OpenAI-compatible LLM provider

Lets the script-writing steps run on an OSS model served on the DGX (e.g. vLLM/Ollama exposing `/v1/chat/completions`) instead of Claude. Independent of Tasks 1–8 — the explainer already works with the existing Claude provider.

**Files:**
- Create: `src/hubed_audio_learn/providers/llm/openai_compat.py`
- Modify: `src/hubed_audio_learn/providers/llm/__init__.py`
- Modify: `src/hubed_audio_learn/config.py` (+ `tests/test_config.py`)
- Test: `tests/test_openai_compat_provider.py`

- [ ] **Step 1: Add config fields** in `config.py` (model + populate in `load_config`):

```python
    oss_llm_base_url: str = "http://localhost:11434/v1"
    oss_llm_model: str = "qwen2.5:14b"
    oss_llm_api_key: str = "not-needed"
```

```python
        oss_llm_base_url=os.environ.get("OSS_LLM_BASE_URL", "http://localhost:11434/v1"),
        oss_llm_model=os.environ.get("OSS_LLM_MODEL", "qwen2.5:14b"),
        oss_llm_api_key=os.environ.get("OSS_LLM_API_KEY", "not-needed"),
```

- [ ] **Step 2: Write the failing test** — `tests/test_openai_compat_provider.py`:

```python
"""OpenAI-compatible LLM provider tests with a mocked httpx client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from hubed_audio_learn.providers.llm.openai_compat import OpenAICompatibleProvider


class _Resp:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_generate_returns_message_content():
    provider = OpenAICompatibleProvider(base_url="http://dgx:8000/v1", model="qwen2.5:14b", api_key="x")
    fake = MagicMock()
    fake.post.return_value = _Resp('{"ok": true}')
    fake.__enter__.return_value = fake
    fake.__exit__.return_value = False
    with patch("hubed_audio_learn.providers.llm.openai_compat.httpx.Client", return_value=fake):
        out = provider.generate("hello")
    assert out == '{"ok": true}'
    body = fake.post.call_args.kwargs["json"]
    assert body["model"] == "qwen2.5:14b"
    assert body["messages"][0]["content"] == "hello"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_openai_compat_provider.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 4: Create `src/hubed_audio_learn/providers/llm/openai_compat.py`**

```python
"""OpenAI-compatible chat-completions LLM provider (for OSS models on the DGX)."""
from __future__ import annotations

from typing import Iterable

import httpx

from hubed_audio_learn.providers.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    name = "openai"

    def __init__(self, base_url: str, model: str, api_key: str = "not-needed"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def generate(
        self,
        prompt: str,
        *,
        allowed_tools: Iterable[str] | None = None,  # OSS path has no tool use; ignored
        timeout_seconds: int = 600,
    ) -> str:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
```

- [ ] **Step 5: Register in the loader** `src/hubed_audio_learn/providers/llm/__init__.py`. Change `load_llm_provider`'s signature to accept the OSS settings and add a branch:

```python
def load_llm_provider(name: str, *, claude_bin: str = "claude",
                      oss_base_url: str = "", oss_model: str = "", oss_api_key: str = "not-needed") -> LLMProvider:
    if name == "claude":
        return ClaudeProvider(binary=claude_bin)
    if name in ("openai", "oss"):
        from hubed_audio_learn.providers.llm.openai_compat import OpenAICompatibleProvider
        return OpenAICompatibleProvider(base_url=oss_base_url, model=oss_model, api_key=oss_api_key)
    raise ValueError(f"Unknown LLM provider: {name!r}. Supported: 'claude', 'openai'.")
```

Update the two CLI call sites (`_cmd_podcast`, `_cmd_explain`) to pass the OSS settings:

```python
    llm = load_llm_provider(cfg.llm_provider, claude_bin=cfg.claude_bin,
                            oss_base_url=cfg.oss_llm_base_url, oss_model=cfg.oss_llm_model,
                            oss_api_key=cfg.oss_llm_api_key)
```

- [ ] **Step 6: Run the provider test + full suite**

Run: `python -m pytest tests/test_openai_compat_provider.py -v && python -m pytest -q`
Expected: new test passes; whole suite green.

- [ ] **Step 7: Commit**

```bash
git add src/hubed_audio_learn/providers/llm/openai_compat.py src/hubed_audio_learn/providers/llm/__init__.py src/hubed_audio_learn/config.py src/hubed_audio_learn/cli.py tests/test_openai_compat_provider.py tests/test_config.py
git commit -m "feat: OpenAI-compatible LLM provider for OSS models"
```

---

## Task 10: Docs, env example, doctor, and manual smoke test

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `src/hubed_audio_learn/cli.py` (`_cmd_doctor`)
- Test: `tests/test_cli.py` (doctor assertion)

- [ ] **Step 1: Extend `.env.example`** with the new settings and comments:

```
# --- Explainer mode (single narrator, OSS TTS) ---
# Kokoro server exposing the OpenAI-compatible /v1/audio/speech route (e.g. Kokoro-FastAPI on the DGX).
KOKORO_URL=http://localhost:8880
KOKORO_VOICE=af_heart
KOKORO_MODEL=kokoro
NARRATOR_NAME=Sam
TTS_PROVIDER=kokoro

# --- Optional: run the LLM on an OSS model instead of Claude ---
# LLM_PROVIDER=openai
# OSS_LLM_BASE_URL=http://localhost:11434/v1
# OSS_LLM_MODEL=qwen2.5:14b
# OSS_LLM_API_KEY=not-needed
```

- [ ] **Step 2: Add a doctor check for Kokoro reachability.** In `_cmd_doctor`, after the ffmpeg check, add a non-fatal probe (does not fail `doctor` if down — it is only needed for explain mode):

```python
    if cfg.tts_provider == "kokoro":
        try:
            import httpx
            r = httpx.get(f"{cfg.kokoro_url.rstrip('/')}/v1/models", timeout=3)
            print(f"Kokoro server: reachable at {cfg.kokoro_url} (HTTP {r.status_code})")
        except Exception as exc:  # noqa: BLE001 - diagnostic only
            print(f"Kokoro server: NOT reachable at {cfg.kokoro_url} ({type(exc).__name__})")
```

- [ ] **Step 3: Update `README.md`** — add an "Explainer mode" section:

```markdown
## Explainer mode (single narrator, open-source TTS)

Generates a single-narrator audio explainer instead of a two-host podcast — denser
and easier to follow for technical topics. Audio is produced by a Kokoro TTS server
(open source) that you run on a GPU box (e.g. a DGX Spark) and reach over HTTP.

1. On the GPU box, run a Kokoro server exposing the OpenAI-compatible TTS API
   (e.g. [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI)) on port 8880.
2. Point the CLI at it and pick the explainer TTS:

   ```bash
   export KOKORO_URL=http://<dgx-host>:8880
   export TTS_PROVIDER=kokoro
   audio-learn explain "mechanistic interpretability" --length medium
   ```

The output MP3 + synced-slide HTML land in `OUTPUT_DIR`, same as podcast mode.
Per-segment synthesis means slide timing is exact (no silence-detection heuristic).
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Manual smoke test (real providers, not in CI)**

```bash
pip install -e .
# Start Kokoro-FastAPI on the DGX, then:
export KOKORO_URL=http://<dgx-host>:8880 TTS_PROVIDER=kokoro
audio-learn doctor                      # expect "Kokoro server: reachable"
audio-learn explain "mechanistic interpretability" --length short
```

Expected: an MP3 + HTML in `OUTPUT_DIR`; opening the HTML plays audio and highlights/advances slides in sync. Note any failures for follow-up.

- [ ] **Step 6: Commit**

```bash
git add .env.example README.md src/hubed_audio_learn/cli.py tests/test_cli.py
git commit -m "docs: explainer mode usage, env example, and Kokoro doctor check"
```

---

## Notes / decisions

- **Why per-segment synthesis:** Kokoro is single-speaker, so we synthesize each segment separately and concatenate. The cumulative clip duration *is* the next segment's start offset, so `timing.json` is exact — this deletes the podcast path's silence-detection fragility (review finding #6) for the explainer path.
- **Why the OpenAI-compatible TTS contract:** Kokoro-FastAPI and several other Kokoro servers expose `/v1/audio/speech`. Using that wire format keeps the provider server-agnostic and mirrors the OSS LLM provider's `/v1/chat/completions`.
- **Reused unchanged:** `research`, `outline`, the `player.html.j2` template, the synced-slide JS, and `SlideMarker`. The explainer reuses the `Timing` schema (`turns` = segments).
- **Not in scope:** streaming TTS, multi-speaker OSS (VibeVoice/Dia2) — those remain a future "podcast-on-OSS" plan. The HTML `</script>` escaping (finding #2) and unguarded-response hardening still apply broadly and are tracked separately in `docs/review-2026-05-24.md`.
```
