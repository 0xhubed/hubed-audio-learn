"""Unit tests for Gemini TTS provider with the SDK mocked.

We assert the script→prompt formatting and the timing-recovery fallback
without making a real network call.
"""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import numpy as np

from hubed_audio_learn.providers.tts.gemini import (
    GeminiTTSProvider,
    _format_dialogue_prompt,
    _recover_turn_timings,
)
from hubed_audio_learn.schemas import Host, Script, Turn


def _make_script(num_turns: int = 3) -> Script:
    return Script(
        outline_ref="outline.json",
        host_a=Host(name="Alex", voice_id="gemini:Charon", persona="curious"),
        host_b=Host(name="Sam", voice_id="gemini:Leda", persona="explainer"),
        turns=[
            Turn(speaker="A" if i % 2 == 0 else "B", text=f"Turn {i}.", section_ref="intro")
            for i in range(num_turns)
        ],
    )


def test_format_dialogue_prompt_tags_speakers():
    script = _make_script(2)
    prompt = _format_dialogue_prompt(script)
    assert "[S1] Turn 0." in prompt
    assert "[S2] Turn 1." in prompt


def test_recover_turn_timings_uses_silence_splits_when_count_matches():
    # 24 kHz mono, 6 seconds total, three "turns" separated by silence at 2s and 4s
    sr = 24000
    total = np.zeros(sr * 6, dtype=np.float32)
    total[0:sr] = 0.5             # 0..1s burst -> turn 0
    total[sr * 2:sr * 3] = 0.5    # 2..3s burst -> turn 1
    total[sr * 4:sr * 5] = 0.5    # 4..5s burst -> turn 2

    timings = _recover_turn_timings(total, sr, num_turns=3)
    starts = [t.start_seconds for t in timings.turns]
    assert starts[0] == 0.0
    assert 1.5 < starts[1] < 2.5
    assert 3.5 < starts[2] < 4.5


def test_recover_turn_timings_falls_back_when_split_count_mismatches():
    sr = 24000
    flat = np.full(sr * 6, 0.5, dtype=np.float32)  # no silences detectable
    script = _make_script(3)
    char_counts = [len(t.text) for t in script.turns]
    timings = _recover_turn_timings(flat, sr, num_turns=3, fallback_char_counts=char_counts)
    starts = [t.start_seconds for t in timings.turns]
    assert starts == sorted(starts)
    assert starts[0] == 0.0
    assert starts[-1] < 6.0


def test_render_calls_sdk_and_returns_mp3_bytes():
    provider = GeminiTTSProvider(api_key="k", model="gemini-2.5-flash-preview-tts")
    script = _make_script(2)

    # Fake 1 second of audio at 24 kHz
    sr = 24000
    pcm_int16 = (np.zeros(sr, dtype=np.int16)).tobytes()
    fake_response = MagicMock()
    fake_response.candidates = [
        MagicMock(content=MagicMock(parts=[MagicMock(inline_data=MagicMock(data=pcm_int16))]))
    ]

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with patch("hubed_audio_learn.providers.tts.gemini.genai.Client", return_value=fake_client), \
         patch("hubed_audio_learn.providers.tts.gemini._pcm_to_mp3", return_value=b"ID3\x00MP3DATA"):
        mp3, timing = provider.render(script)

    assert mp3 == b"ID3\x00MP3DATA"
    assert len(timing.turns) == 2
    fake_client.models.generate_content.assert_called_once()
