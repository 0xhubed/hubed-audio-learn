"""Schema for script.json — Stage 3 output (podcast path)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Host(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    voice_id: str
    persona: str


class SlideMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")
    figure_id: str
    cue: Literal["hard", "soft"] = "soft"


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speaker: Literal["A", "B"]
    text: str
    section_ref: str
    slide_marker: SlideMarker | None = None


class Script(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outline_ref: str
    host_a: Host
    host_b: Host
    turns: list[Turn]
