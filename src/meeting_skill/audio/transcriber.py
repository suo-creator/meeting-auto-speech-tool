from __future__ import annotations

import json
import os
import shutil
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from meeting_skill.config import get_settings, project_path
from meeting_skill.models.types import TranscriptSegment


TEXT_INPUT_SUFFIXES = {".txt", ".md"}
WHISPER_PROVIDERS = {"whisper", "whisper-local", "local-whisper", "openai-whisper"}
OPENAI_COMPATIBLE_PROVIDERS = {"openai-compatible", "openai", "remote", "api"}


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def resolve_audio_path(audio_path: Path) -> Path:
    if audio_path.exists():
        return audio_path.resolve()

    candidates: list[Path] = []
    if not audio_path.is_absolute():
        candidates.extend(
            [
                project_path(str(audio_path)),
                Path.cwd() / audio_path,
            ]
        )

    candidates.extend(
        [
            project_path("data", "cache", audio_path.name),
            project_path("data", "input", audio_path.name),
            project_path("dist", "data", "cache", audio_path.name),
            project_path("dist", "data", "input", audio_path.name),
        ]
    )

    for root in [
        project_path("data", "cache", "sessions"),
        project_path("dist", "data", "cache", "sessions"),
        project_path("dist", "data", "cache"),
        project_path("data", "cache"),
    ]:
        if root.exists():
            matches = sorted(root.rglob(audio_path.name), key=lambda item: item.stat().st_mtime, reverse=True)
            candidates.extend(matches)

    candidates = _dedupe_paths(candidates)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    searched = [str(audio_path), *(str(candidate) for candidate in candidates)]
    raise FileNotFoundError("Input file does not exist. Searched: " + "; ".join(searched))


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    provider: str
    model: str
    diagnostics: list[str]


def _segments_from_text(text: str) -> list[TranscriptSegment]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    segments: list[TranscriptSegment] = []
    for idx, line in enumerate(lines):
        speaker = "Speaker 1"
        content = line
        if ":" in line:
            maybe_speaker, maybe_content = line.split(":", 1)
            if len(maybe_speaker) <= 24:
                speaker = maybe_speaker.strip()
                content = maybe_content.strip()
        if content:
            segments.append(TranscriptSegment(start=idx * 8.0, end=(idx + 1) * 8.0, speaker=speaker, text=content))
    return segments


def analyze_wav(audio_path: Path) -> list[str]:
    if audio_path.suffix.lower() != ".wav":
        return []
    diagnostics: list[str] = []
    try:
        with wave.open(str(audio_path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()
            duration = frames / sample_rate if sample_rate else 0.0
            diagnostics.append(
                f"wav: duration={duration:.2f}s, channels={channels}, sample_rate={sample_rate}, sample_width={sample_width}"
            )
            if frames == 0 or duration < 0.2:
                diagnostics.append("wav_warning: audio is empty or too short")
            if sample_width != 2:
                diagnostics.append("wav_warning: expected 16-bit PCM; non-16-bit audio may reduce compatibility")
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(f"wav_warning: failed to inspect wav metadata: {exc}")
    return diagnostics


def transcribe_mock(audio_path: Path) -> TranscriptionResult:
    if audio_path.suffix.lower() in TEXT_INPUT_SUFFIXES:
        segments = _segments_from_text(audio_path.read_text(encoding="utf-8"))
        return TranscriptionResult(segments, "mock", "text-parser", [f"text_input: parsed {len(segments)} text lines"])
    return TranscriptionResult([], "mock", "none", ["mock_audio: no speech model configured; audio transcription returns empty"])


def _normalize_whisper_model(model_name: str) -> str:
    normalized = (model_name or "base").strip().replace("whisper-", "")
    if normalized in {"", "local"}:
        return "base"
    return normalized


def ensure_ffmpeg_path(diagnostics: list[str]) -> None:
    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["FFMPEG_BINARY"] = ffmpeg_exe
        ffmpeg_bin_dir = project_path(".local", "ffmpeg")
        ffmpeg_bin_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_cmd = ffmpeg_bin_dir / "ffmpeg.exe"
        if not ffmpeg_cmd.exists():
            shutil.copy2(ffmpeg_exe, ffmpeg_cmd)
        path_parts = os.environ.get("PATH", "").split(os.pathsep)
        if str(ffmpeg_bin_dir) not in path_parts:
            os.environ["PATH"] = str(ffmpeg_bin_dir) + os.pathsep + os.environ.get("PATH", "")
        diagnostics.append(f"ffmpeg: using {ffmpeg_cmd}")
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(f"ffmpeg_warning: imageio-ffmpeg unavailable: {exc}")


def transcribe_with_whisper(audio_path: Path) -> TranscriptionResult:
    settings = get_settings()
    model_name = _normalize_whisper_model(settings.speech_model)
    diagnostics = analyze_wav(audio_path)
    ensure_ffmpeg_path(diagnostics)
    try:
        import whisper
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(f"whisper_import_error: {exc}")
        diagnostics.append("fix: run `scripts\\setup.bat`; direct system Python may not have whisper/torch installed")
        return TranscriptionResult([], "whisper-local", model_name, diagnostics)

    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(str(audio_path), verbose=False, language=None, fp16=False)
        segments: list[TranscriptSegment] = []
        for idx, item in enumerate(result.get("segments", [])):
            text = str(item.get("text", "")).strip()
            if text:
                segments.append(
                    TranscriptSegment(
                        start=float(item.get("start", 0.0)),
                        end=float(item.get("end", 0.0)),
                        speaker=f"Speaker {(idx % 2) + 1}",
                        text=text,
                    )
                )
        language = result.get("language", "unknown")
        diagnostics.append(f"whisper_result: language={language}, segments={len(segments)}")
        if not segments:
            diagnostics.append("whisper_empty: model returned no text; check volume, microphone selection, language clarity, and ffmpeg availability")
        return TranscriptionResult(segments, "whisper-local", model_name, diagnostics)
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(f"whisper_runtime_error: {exc}")
        diagnostics.append("fix: verify ffmpeg is available through imageio-ffmpeg; verify the Whisper model can be downloaded/loaded")
        return TranscriptionResult([], "whisper-local", model_name, diagnostics)


def transcribe_with_openai_compatible(audio_path: Path) -> TranscriptionResult:
    settings = get_settings()
    diagnostics = analyze_wav(audio_path)
    if not settings.speech_base_url or not settings.speech_api_key:
        diagnostics.append("api_config_error: SPEECH_BASE_URL or SPEECH_API_KEY is empty")
        return TranscriptionResult([], "openai-compatible", settings.speech_model, diagnostics)
    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(f"requests_import_error: {exc}")
        diagnostics.append("fix: run `scripts\\setup.bat` or use `scripts\\meeting.bat`, not system python directly")
        return TranscriptionResult([], "openai-compatible", settings.speech_model, diagnostics)

    last_error = None
    for attempt in range(1, 4):
        try:
            with audio_path.open("rb") as file:
                response = requests.post(
                    f"{settings.speech_base_url.rstrip('/')}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.speech_api_key}"},
                    files={"file": file},
                    data={"model": settings.speech_model, "response_format": "verbose_json"},
                    timeout=300,
                )
            response.raise_for_status()
            data = response.json()
            raw_segments = data.get("segments") or [{"start": 0, "end": 0, "text": data.get("text", "")}]
            segments = [
                TranscriptSegment(
                    float(item.get("start", 0)),
                    float(item.get("end", 0)),
                    f"Speaker {(idx % 2) + 1}",
                    str(item.get("text", "")).strip(),
                )
                for idx, item in enumerate(raw_segments)
                if str(item.get("text", "")).strip()
            ]
            diagnostics.append(f"api_result: status={response.status_code}, segments={len(segments)}, attempt={attempt}")
            return TranscriptionResult(segments, "openai-compatible", settings.speech_model, diagnostics)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            diagnostics.append(f"api_attempt_{attempt}_error: {exc}")
            time.sleep(min(2 * attempt, 5))
    diagnostics.append(f"api_runtime_error: {last_error}")
    diagnostics.append("fix: stream disconnected means the remote/local service closed the connection; check that 127.0.0.1 service is running and supports the requested endpoint")
    return TranscriptionResult([], "openai-compatible", settings.speech_model, diagnostics)


def transcribe_audio_file_result(audio_path: Path) -> TranscriptionResult:
    settings = get_settings()
    provider = settings.speech_provider.strip().lower()
    audio_path = resolve_audio_path(audio_path)
    if audio_path.suffix.lower() in TEXT_INPUT_SUFFIXES:
        segments = _segments_from_text(audio_path.read_text(encoding="utf-8"))
        return TranscriptionResult(segments, "text", "text-parser", [f"text_input: parsed {len(segments)} text lines"])
    if provider in WHISPER_PROVIDERS:
        return transcribe_with_whisper(audio_path)
    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        return transcribe_with_openai_compatible(audio_path)
    result = transcribe_mock(audio_path)
    result.diagnostics.insert(0, f"provider_warning: unsupported SPEECH_PROVIDER={settings.speech_provider!r}; used mock mode")
    result.diagnostics.append("fix: set SPEECH_PROVIDER=whisper-local or SPEECH_PROVIDER=openai-compatible")
    return result


def transcribe_audio_file(audio_path: Path) -> list[TranscriptSegment]:
    return transcribe_audio_file_result(audio_path).segments


def write_segments_jsonl(segments: list[TranscriptSegment], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for segment in segments:
            file.write(json.dumps(segment.to_dict(), ensure_ascii=False) + "\n")
