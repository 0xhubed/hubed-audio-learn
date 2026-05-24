"""Gemini multi-speaker TTS provider.

Gemini's TTS API returns a single raw PCM stream for the whole dialogue.
We recover per-turn start offsets via silence detection on the waveform.
When silence detection does not yield a clean split, we fall back to
character-proportional timing — coarse but safe.
"""
from __future__ import annotations

import io
from typing import Sequence

import numpy as np
from google import genai
from google.genai import types as genai_types
from pydub import AudioSegment

from hubed_audio_learn.providers.tts.base import TTSProvider
from hubed_audio_learn.schemas import Script, Timing, TurnTiming

_SAMPLE_RATE_HZ = 24000  # Gemini TTS PCM output
_SILENCE_TOP_DB = 30     # librosa.effects.split threshold


def _format_dialogue_prompt(script: Script) -> str:
    """Tag each turn with [S1] (host A) or [S2] (host B), one per line."""
    lines = []
    for turn in script.turns:
        tag = "[S1]" if turn.speaker == "A" else "[S2]"
        lines.append(f"{tag} {turn.text}")
    return "\n".join(lines)


def _recover_turn_timings(
    audio: np.ndarray,
    sample_rate: int,
    num_turns: int,
    fallback_char_counts: Sequence[int] | None = None,
) -> Timing:
    """Detect non-silent intervals via librosa; fall back to character-proportional.

    Returns a Timing with exactly `num_turns` entries.
    """
    import librosa  # heavy import — kept local

    intervals = librosa.effects.split(audio, top_db=_SILENCE_TOP_DB)
    if len(intervals) == num_turns:
        starts = [float(start) / sample_rate for start, _ in intervals]
        return Timing(turns=[TurnTiming(index=i, start_seconds=round(s, 3)) for i, s in enumerate(starts)])

    total_seconds = len(audio) / sample_rate
    if fallback_char_counts and sum(fallback_char_counts) > 0:
        cumulative = 0
        total_chars = sum(fallback_char_counts)
        starts = []
        for c in fallback_char_counts:
            starts.append(round(cumulative / total_chars * total_seconds, 3))
            cumulative += c
    else:
        per = total_seconds / max(num_turns, 1)
        starts = [round(i * per, 3) for i in range(num_turns)]
    return Timing(turns=[TurnTiming(index=i, start_seconds=s) for i, s in enumerate(starts)])


def _pcm_to_mp3(pcm_int16: bytes, sample_rate: int = _SAMPLE_RATE_HZ) -> bytes:
    """Encode raw 16-bit mono PCM to MP3 via pydub/ffmpeg."""
    segment = AudioSegment(
        data=pcm_int16,
        sample_width=2,
        frame_rate=sample_rate,
        channels=1,
    )
    buf = io.BytesIO()
    segment.export(buf, format="mp3", bitrate="96k")
    return buf.getvalue()


class GeminiTTSProvider(TTSProvider):
    name = "gemini"
    supported_languages = ["en"]

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini TTS provider.")
        self.api_key = api_key
        self.model = model

    def render(self, script: Script) -> tuple[bytes, Timing]:
        client = genai.Client(api_key=self.api_key)
        prompt = _format_dialogue_prompt(script)

        speech_config = genai_types.SpeechConfig(
            multi_speaker_voice_config=genai_types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    genai_types.SpeakerVoiceConfig(
                        speaker="S1",
                        voice_config=genai_types.VoiceConfig(
                            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                                voice_name=script.host_a.voice_id.split(":")[-1],
                            )
                        ),
                    ),
                    genai_types.SpeakerVoiceConfig(
                        speaker="S2",
                        voice_config=genai_types.VoiceConfig(
                            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                                voice_name=script.host_b.voice_id.split(":")[-1],
                            )
                        ),
                    ),
                ]
            )
        )

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config,
            ),
        )

        pcm_bytes = response.candidates[0].content.parts[0].inline_data.data
        pcm_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        char_counts = [len(t.text) for t in script.turns]
        timing = _recover_turn_timings(
            pcm_array,
            sample_rate=_SAMPLE_RATE_HZ,
            num_turns=len(script.turns),
            fallback_char_counts=char_counts,
        )
        mp3 = _pcm_to_mp3(pcm_bytes)
        return mp3, timing
