from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from rich import print

from meeting_skill.audio.recorder import create_recording_session_dir, live_record_and_transcribe
from meeting_skill.audio.transcriber import analyze_wav, resolve_audio_path, transcribe_audio_file, transcribe_audio_file_result, write_segments_jsonl
from meeting_skill.config import ENV_FILE, get_settings, project_path
from meeting_skill.exporters.archive import create_archive_dir, export_minutes, export_transcript
from meeting_skill.models.types import TranscriptSegment
from meeting_skill.rag.meeting_rag import TemporaryMeetingRag
from meeting_skill.text.summarizer import MinutesEngine
from meeting_skill.workflow import EmptyTranscriptError, MeetingWorkflow, latest_archive

app = typer.Typer(help="Meeting real-time transcription, minutes generation, RAG QA and archive automation.")


def _load_segments(path: Path) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                segments.append(TranscriptSegment(**json.loads(line)))
    return segments


@app.command()
def run_file(
    input_path: Path,
    title: str = "meeting",
    question: list[str] = typer.Option(None, "--question", "-q", help="Optional meeting QA question to run before export."),
) -> None:
    workflow = MeetingWorkflow(title)
    try:
        outputs = workflow.run_from_file(input_path, questions=question or [])
    except (EmptyTranscriptError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    print(f"[green]Meeting workflow completed[/green]: {workflow.archive_dir}")
    for name, path in outputs.items():
        print(f"{name}: {path}")


@app.command()
def transcribe(
    input_path: Path,
    output_jsonl: Path = typer.Option(project_path("data", "cache", "transcript.jsonl")),
    debug: bool = typer.Option(False, "--debug", help="Print speech provider diagnostics."),
) -> None:
    result = transcribe_audio_file_result(input_path)
    segments = result.segments
    write_segments_jsonl(segments, output_jsonl)
    if not segments:
        print("[yellow]No valid speech recognized. Empty transcript saved.[/yellow]")
    if debug or not segments:
        print(f"[cyan]provider[/cyan]: {result.provider}")
        print(f"[cyan]model[/cyan]: {result.model}")
        for item in result.diagnostics:
            print(f"[cyan]diagnostic[/cyan]: {item}")
    for segment in segments:
        print(segment.to_markdown())
    print(f"[green]Saved[/green]: {output_jsonl}")


@app.command()
def record(
    seconds: int = typer.Option(60, help="Maximum recording duration. Press Enter or Ctrl+C to stop early."),
    chunk_seconds: int = typer.Option(30, help="Audio chunk duration before each transcription pass."),
    cache_jsonl: Path | None = typer.Option(None, help="Transcript JSONL cache path. Defaults to a new timestamped session."),
) -> None:
    if cache_jsonl is None:
        cache_jsonl = create_recording_session_dir() / "live_cache.jsonl"
    segments = live_record_and_transcribe(cache_jsonl, seconds=seconds, chunk_seconds=chunk_seconds)
    print(f"[green]Recorded segments[/green]: {len(segments)}")


@app.command()
def doctor(input_path: Path | None = typer.Argument(None, help="Optional audio file to inspect.")) -> None:
    settings = get_settings()
    print(f"config_env: {ENV_FILE} (exists={ENV_FILE.exists()})")
    print(f"speech_provider: {settings.speech_provider}")
    print(f"speech_model: {settings.speech_model}")
    print(f"speech_base_url: {settings.speech_base_url or '<empty>'}")
    ffmpeg_in_path = shutil.which('ffmpeg')
    if ffmpeg_in_path:
        print(f"ffmpeg: {ffmpeg_in_path}")
    else:
        try:
            import imageio_ffmpeg

            print(f"ffmpeg: imageio-ffmpeg available at {imageio_ffmpeg.get_ffmpeg_exe()}")
        except Exception:
            print("ffmpeg: <not found in PATH>")
    try:
        import whisper  # noqa: F401

        print("whisper: installed")
    except Exception as exc:  # noqa: BLE001
        print(f"whisper: missing ({exc})")
    try:
        import torch

        print(f"torch: installed ({torch.__version__})")
    except Exception as exc:  # noqa: BLE001
        print(f"torch: missing ({exc})")
    if input_path is not None:
        try:
            resolved = resolve_audio_path(input_path)
            print(f"audio_path: {resolved}")
            for item in analyze_wav(resolved):
                print(f"audio: {item}")
            result = transcribe_audio_file_result(resolved)
            print(f"transcribe_provider: {result.provider}")
            print(f"transcribe_model: {result.model}")
            print(f"transcribe_segments: {len(result.segments)}")
            for item in result.diagnostics:
                print(f"diagnostic: {item}")
        except Exception as exc:  # noqa: BLE001
            print(f"audio_error: {exc}")


@app.command()
def summarize(transcript_jsonl: Path, output_md: Path = typer.Option(project_path("data", "cache", "minutes.md"))) -> None:
    segments = _load_segments(transcript_jsonl)
    minutes = MinutesEngine().summarize(segments)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(minutes, encoding="utf-8")
    print(minutes)
    print(f"[green]Saved[/green]: {output_md}")


@app.command()
def ask(transcript_jsonl: Path, question: str) -> None:
    segments = _load_segments(transcript_jsonl)
    answer = TemporaryMeetingRag(segments).ask(question)
    print(json.dumps(answer, ensure_ascii=False, indent=2))


@app.command()
def archive(transcript_jsonl: Path, minutes_md: Path, title: str = "meeting") -> None:
    segments = _load_segments(transcript_jsonl)
    minutes = minutes_md.read_text(encoding="utf-8")
    archive_dir = create_archive_dir(title)
    outputs = export_transcript(segments, archive_dir)
    outputs["minutes"] = export_minutes(minutes, archive_dir)
    print(f"[green]Archived[/green]: {archive_dir}")
    for name, path in outputs.items():
        print(f"{name}: {path}")


@app.command()
def latest() -> None:
    path = latest_archive()
    print(path or "No archive yet")


if __name__ == "__main__":
    app()
