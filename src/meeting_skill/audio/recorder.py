from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable


def _find_project_root(start: Path) -> Path:
    explicit_root = os.environ.get("MEETING_SKILL_ROOT")
    if explicit_root:
        return Path(explicit_root).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    for candidate in [start, *start.parents]:
        if (candidate / "src" / "meeting_skill").exists() and (candidate / "config").exists():
            return candidate
    raise RuntimeError("Cannot locate meeting-auto-skill project root.")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
SRC_DIR = PROJECT_ROOT / "src"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

if __package__ in {None, ""}:
    if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve() and os.environ.get("MEETING_SKILL_NO_REEXEC") != "1":
        env = os.environ.copy()
        env["MEETING_SKILL_NO_REEXEC"] = "1"
        env["MEETING_SKILL_ROOT"] = str(PROJECT_ROOT)
        env["PYTHONPATH"] = str(SRC_DIR)
        raise SystemExit(subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=str(PROJECT_ROOT), env=env))
    sys.path.insert(0, str(SRC_DIR))

from meeting_skill.audio.cache import TranscriptCache
from meeting_skill.audio.transcriber import transcribe_audio_file_result
from meeting_skill.config import get_settings, project_path
from meeting_skill.models.types import TranscriptSegment


class RecorderError(RuntimeError):
    pass


ProgressCallback = Callable[[float, float], None]


def _record_microphone_capture(
    output_wav: Path,
    seconds: int,
    stop_event: threading.Event | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, float]:
    settings = get_settings()
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    if seconds <= 0:
        raise RecorderError("Recording duration must be greater than zero seconds.")

    stop_event = stop_event or threading.Event()
    try:
        import numpy as np
        import sounddevice as sd
        import soundfile as sf

        frames_buffer: list[np.ndarray] = []

        def callback(indata, frame_count, time_info, status) -> None:  # noqa: ANN001
            if status:
                print(f"\n[record warning] {status}")
            frames_buffer.append(indata.copy())

        started = time.monotonic()
        last_progress = -1
        with sd.InputStream(
            samplerate=settings.record_sample_rate,
            channels=settings.record_channels,
            dtype="float32",
            callback=callback,
        ):
            while not stop_event.is_set():
                elapsed = time.monotonic() - started
                if elapsed >= seconds:
                    break
                current_second = int(elapsed)
                if progress_callback and current_second != last_progress:
                    progress_callback(elapsed, seconds)
                    last_progress = current_second
                time.sleep(0.1)

        if not frames_buffer:
            raise RecorderError("No audio frames captured. Check microphone device and permissions.")
        audio = np.concatenate(frames_buffer, axis=0)
        recorded_seconds = len(audio) / float(settings.record_sample_rate)
        sf.write(str(output_wav), audio, settings.record_sample_rate)
        return output_wav, recorded_seconds
    except RecorderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RecorderError(f"Microphone recording failed: {exc}") from exc


def record_microphone(output_wav: Path, seconds: int) -> Path:
    path, _ = _record_microphone_capture(output_wav, seconds)
    return path


def _start_enter_stop_listener(stop_event: threading.Event) -> threading.Thread:
    def wait_for_enter() -> None:
        try:
            input()
            stop_event.set()
        except EOFError:
            pass

    thread = threading.Thread(target=wait_for_enter, daemon=True)
    thread.start()
    return thread


def _print_startup(cache_path: Path, seconds: int, chunk_seconds: int) -> None:
    settings = get_settings()
    print("=" * 72)
    print("Meeting live recording/transcription started")
    print(f"Python: {sys.executable}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Max duration: {seconds}s")
    print(f"Chunk duration: {chunk_seconds}s")
    print(f"Sample rate/channels: {settings.record_sample_rate} Hz / {settings.record_channels}")
    print(f"Speech provider/model: {settings.speech_provider} / {settings.speech_model}")
    print(f"Live cache: {cache_path}")
    print("Stop shortcut: press Enter to stop, or Ctrl+C to interrupt and save cache")
    print("=" * 72)


def create_recording_session_dir(base_dir: Path | None = None) -> Path:
    root = base_dir or project_path("data", "cache", "sessions")
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = root / stamp
    counter = 1
    while session_dir.exists():
        session_dir = root / f"{stamp}_{counter:02d}"
        counter += 1
    session_dir.mkdir(parents=True, exist_ok=False)
    return session_dir


def live_record_and_transcribe(
    cache_path: Path,
    seconds: int = 60,
    chunk_seconds: int = 30,
    interactive: bool = True,
    stop_event: threading.Event | None = None,
) -> list[TranscriptSegment]:
    if seconds <= 0 or chunk_seconds <= 0:
        raise RecorderError("seconds and chunk_seconds must be positive integers.")

    stop_event = stop_event or threading.Event()
    if interactive:
        _print_startup(cache_path, seconds, chunk_seconds)
        _start_enter_stop_listener(stop_event)

    cache = TranscriptCache(cache_path, flush_seconds=get_settings().cache_flush_seconds)
    segments: list[TranscriptSegment] = []
    started = time.monotonic()
    elapsed_audio = 0.0
    work_queue: queue.Queue[tuple[Path, float]] = queue.Queue()

    try:
        current = 0
        while time.monotonic() - started < seconds and not stop_event.is_set():
            elapsed = int(time.monotonic() - started)
            remaining = max(1, seconds - elapsed)
            duration = min(chunk_seconds, remaining)
            wav_path = cache_path.parent / f"live_chunk_{current:04d}.wav"

            if interactive:
                print(f"\n[record] Start chunk {current + 1}, target {duration}s -> {wav_path.name}")

            def progress(recorded: float, total: float) -> None:
                if interactive:
                    print(f"\r[recording] chunk {current + 1}: {recorded:0.0f}/{total:0.0f}s, press Enter to stop...", end="", flush=True)

            chunk_path, recorded_seconds = _record_microphone_capture(
                wav_path,
                duration,
                stop_event=stop_event,
                progress_callback=progress,
            )
            if recorded_seconds <= 0.05:
                break
            if interactive:
                print(f"\n[record] Chunk {current + 1} saved, actual duration {recorded_seconds:0.1f}s")
            work_queue.put((chunk_path, elapsed_audio))
            elapsed_audio += recorded_seconds

            while not work_queue.empty():
                chunk, offset = work_queue.get()
                if interactive:
                    print(f"[transcribe] Processing {chunk.name} ...")
                result = transcribe_audio_file_result(chunk)
                if result.diagnostics and interactive:
                    for item in result.diagnostics:
                        print(f"[diagnostic] {item}")
                if not result.segments and interactive:
                    print(f"[transcribe] No valid speech recognized in {chunk.name}")
                for seg in result.segments:
                    adjusted = TranscriptSegment(seg.start + offset, seg.end + offset, seg.speaker, seg.text)
                    cache.append(adjusted, force=True)
                    segments.append(adjusted)
                    print(f"[live transcript] {adjusted.to_markdown()}")
            current += 1
    except KeyboardInterrupt:
        stop_event.set()
        print("\n[stop] Ctrl+C received. Saving cached transcript...")
        cache.flush()
    except Exception:
        cache.flush()
        raise

    cache.flush()
    if interactive:
        print("\n" + "=" * 72)
        print(f"Recording/transcription finished. Transcript segments: {len(segments)}")
        print(f"Cache file: {cache_path}")
        print("=" * 72)
    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive microphone recording and live transcription.")
    parser.add_argument("--seconds", type=int, default=3600, help="Maximum recording duration in seconds.")
    parser.add_argument("--chunk-seconds", type=int, default=30, help="Audio chunk duration before transcription.")
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=None,
        help="Transcript JSONL cache path.",
    )
    args = parser.parse_args()
    if args.cache_path is None:
        cache_path = create_recording_session_dir() / "live_cache.jsonl"
    else:
        cache_path = args.cache_path if args.cache_path.is_absolute() else project_path(str(args.cache_path))
    live_record_and_transcribe(cache_path, seconds=args.seconds, chunk_seconds=args.chunk_seconds, interactive=True)


if __name__ == "__main__":
    main()
