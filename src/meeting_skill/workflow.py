from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from meeting_skill.audio.cache import TranscriptCache
from meeting_skill.audio.recorder import live_record_and_transcribe
from meeting_skill.audio.transcriber import transcribe_audio_file_result
from meeting_skill.config import get_settings, project_path
from meeting_skill.exporters.archive import create_archive_dir, export_minutes, export_qa_history, export_todos, export_transcript
from meeting_skill.models.types import TranscriptSegment
from meeting_skill.rag.meeting_rag import TemporaryMeetingRag
from meeting_skill.text.summarizer import MinutesEngine


class EmptyTranscriptError(RuntimeError):
    pass


class MeetingWorkflow:
    def __init__(self, meeting_title: str = "meeting") -> None:
        self.meeting_title = meeting_title
        self.settings = get_settings()
        self.archive_dir = create_archive_dir(meeting_title)
        self.cache = TranscriptCache(self.archive_dir / "live_cache.jsonl", self.settings.cache_flush_seconds)
        self.qa_history: list[dict[str, object]] = []
        self.segments: list[TranscriptSegment] = []
        self.minutes = ""
        self.rag: TemporaryMeetingRag | None = None

    def _require_segments(self) -> None:
        if not self.segments:
            raise EmptyTranscriptError("No transcript segments were produced. Check the audio file, microphone input, or speech model configuration.")

    def transcribe_file(self, input_path: Path) -> list[TranscriptSegment]:
        try:
            result = transcribe_audio_file_result(input_path)
            self.segments = result.segments
            if not self.segments and result.diagnostics:
                raise EmptyTranscriptError("No transcript segments were produced. " + " | ".join(result.diagnostics))
        except Exception:
            self.segments = self.cache.load_all()
            if not self.segments:
                raise
        self._require_segments()
        for segment in self.segments:
            self.cache.append(segment)
        self.cache.flush()
        return self.segments

    def record_live(self, seconds: int, chunk_seconds: int = 30) -> list[TranscriptSegment]:
        self.segments = live_record_and_transcribe(self.archive_dir / "live_cache.jsonl", seconds=seconds, chunk_seconds=chunk_seconds)
        self._require_segments()
        return self.segments

    def summarize(self) -> str:
        self._require_segments()
        self.minutes = MinutesEngine().summarize(self.segments)
        return self.minutes

    def build_rag(self) -> TemporaryMeetingRag:
        self._require_segments()
        self.rag = TemporaryMeetingRag(self.segments)
        return self.rag

    def ask(self, question: str) -> dict[str, object]:
        if self.rag is None:
            self.build_rag()
        assert self.rag is not None
        answer = self.rag.ask(question)
        self.qa_history.append(answer)
        return answer

    def export_all(self) -> dict[str, Path]:
        self._require_segments()
        outputs = export_transcript(self.segments, self.archive_dir)
        outputs["minutes"] = export_minutes(self.minutes, self.archive_dir)
        outputs["todos"] = export_todos(self.minutes, self.archive_dir)
        outputs["qa_history"] = export_qa_history(self.qa_history, self.archive_dir)
        return outputs

    def run_from_file(self, input_path: Path, questions: list[str] | None = None) -> dict[str, Path]:
        try:
            self.transcribe_file(input_path)
            self.summarize()
            self.build_rag()
            for question in questions or []:
                self.ask(question)
            return self.export_all()
        except Exception:
            if self.archive_dir.exists() and not any(self.archive_dir.iterdir()):
                rmtree(self.archive_dir)
            raise


def latest_archive() -> Path | None:
    root = project_path("archives")
    if not root.exists():
        return None
    dirs = [path for path in root.iterdir() if path.is_dir()]
    return max(dirs, key=lambda path: path.stat().st_mtime) if dirs else None
