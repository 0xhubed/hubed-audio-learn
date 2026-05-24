"""Schema for outline.json — Stage 2 output."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KeyClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    sources: list[str] = Field(default_factory=list)


class Example(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["scenario", "code", "analogy"]
    body: str


class Figure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["diagram", "math-block", "image", "table", "scenario"]
    caption: str
    latex: str | None = None
    body: str | None = None


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    summary: str
    key_claims: list[KeyClaim] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    figures: list[Figure] = Field(default_factory=list)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    url: str
    title: str


class Outline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    language: Literal["en"] = "en"
    target_length: Literal["short", "medium", "long"]
    audience_assumed: str
    learning_objectives: list[str] = Field(default_factory=list)
    sections: list[Section]
    sources_used: list[Source] = Field(default_factory=list)
