"""Pydantic schemas — canonical contracts between pipeline stages."""
from hubed_audio_learn.schemas.outline import Figure, KeyClaim, Outline, Section, Source
from hubed_audio_learn.schemas.research import ResearchBundle, UserDoc, WebSource
from hubed_audio_learn.schemas.script import Host, Script, SlideMarker, Turn
from hubed_audio_learn.schemas.timing import Timing, TurnTiming

__all__ = [
    "Figure",
    "Host",
    "KeyClaim",
    "Outline",
    "ResearchBundle",
    "Script",
    "Section",
    "SlideMarker",
    "Source",
    "Timing",
    "Turn",
    "TurnTiming",
    "UserDoc",
    "WebSource",
]
