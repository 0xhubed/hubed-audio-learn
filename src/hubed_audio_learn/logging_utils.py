"""JSONL structured logger writing to stdout."""
from __future__ import annotations

import json
import sys
import time
from typing import Any


class StageLogger:
    def __init__(self, stage: str, episode_id: str):
        self.stage = stage
        self.episode_id = episode_id
        self.start_ts = time.monotonic()

    def event(self, name: str, **data: Any) -> None:
        record = {
            "ts": time.time(),
            "stage": self.stage,
            "episode_id": self.episode_id,
            "event": name,
            "data": data,
        }
        sys.stdout.write(json.dumps(record) + "\n")
        sys.stdout.flush()

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_ts
