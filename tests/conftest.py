"""Shared pytest fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        with open(FIXTURES / name, "r", encoding="utf-8") as f:
            return json.load(f)
    return _load


@pytest.fixture
def tmp_work_dir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "output"
    d.mkdir()
    return d
