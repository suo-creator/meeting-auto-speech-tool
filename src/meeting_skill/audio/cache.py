from __future__ import annotations

import json
import time
from pathlib import Path

from meeting_skill.models.types import TranscriptSegment


class TranscriptCache:
    def __init__(self, cache_path: Path, flush_seconds: int = 5) -> None:
        self.cache_path = cache_path
        self.flush_seconds = flush_seconds
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.touch(exist_ok=True)
        self._buffer: list[TranscriptSegment] = []
        self._last_flush = time.monotonic()

    def append(self, segment: TranscriptSegment, force: bool = False) -> None:
        self._buffer.append(segment)
        if force or time.monotonic() - self._last_flush >= self.flush_seconds:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            self.cache_path.touch(exist_ok=True)
            return
        with self.cache_path.open("a", encoding="utf-8") as file:
            for segment in self._buffer:
                file.write(json.dumps(segment.to_dict(), ensure_ascii=False) + "\n")
        self._buffer.clear()
        self._last_flush = time.monotonic()

    def load_all(self) -> list[TranscriptSegment]:
        self.flush()
        if not self.cache_path.exists():
            return []
        segments: list[TranscriptSegment] = []
        with self.cache_path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    item = json.loads(line)
                    segments.append(TranscriptSegment(**item))
        return segments
