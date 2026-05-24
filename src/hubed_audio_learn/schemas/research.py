"""Schema for research_bundle.json — Stage 1 output."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    kind: Literal["pdf", "markdown", "text", "rst"]
    extracted_text: str


class WebSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    title: str
    fetched_at: datetime
    content: str


class ResearchBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    user_prompt: str | None = None
    user_docs: list[UserDoc] = Field(default_factory=list)
    web_sources: list[WebSource] = Field(default_factory=list)
    search_queries_used: list[str] = Field(default_factory=list)
