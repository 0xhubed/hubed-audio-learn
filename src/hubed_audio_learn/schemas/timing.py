"""Schema for timing.json — sibling of episode.mp3."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TurnTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int
    start_seconds: float


class Timing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turns: list[TurnTiming]
