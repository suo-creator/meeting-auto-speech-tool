from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class TranscriptSegment:
    start: float
    end: float
    speaker: str
    text: str

    def to_markdown(self) -> str:
        return f"[{self.start:0.1f}s - {self.end:0.1f}s] {self.speaker}: {self.text}"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ModelResult:
    content: str
    provider: str
    model: str
    ok: bool = True
    error: str | None = None
