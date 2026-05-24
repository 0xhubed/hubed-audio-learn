"""TTS dispatcher unit tests with the provider mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from hubed_audio_learn.pipeline.tts import run_tts
from hubed_audio_learn.schemas import Timing, TurnTiming


def test_run_tts_writes_mp3_and_timing(tmp_work_dir: Path, load_fixture):
    script = load_fixture("sample_script.json")
    (tmp_work_dir / "script.json").write_text(json.dumps(script))

    provider = MagicMock()
    provider.render.return_value = (
        b"ID3\x00MP3DATA",
        Timing(turns=[TurnTiming(index=0, start_seconds=0.0),
                      TurnTiming(index=1, start_seconds=3.5),
                      TurnTiming(index=2, start_seconds=8.2)]),
    )

    mp3_path, timing_path = run_tts(work_dir=tmp_work_dir, tts=provider)

    assert mp3_path == tmp_work_dir / "episode.mp3"
    assert timing_path == tmp_work_dir / "timing.json"
    assert mp3_path.read_bytes() == b"ID3\x00MP3DATA"
    timing_data = json.loads(timing_path.read_text())
    assert timing_data["turns"][2]["start_seconds"] == 8.2
    provider.render.assert_called_once()
