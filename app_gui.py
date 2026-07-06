from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Callable


IS_FROZEN = getattr(sys, "frozen", False)


def runtime_base_dir() -> Path:
    if IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_PATH = runtime_base_dir()
os.environ["MEETING_SKILL_ROOT"] = str(BASE_PATH)
SRC_PATH = BASE_PATH / "src"
if not IS_FROZEN and SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))

from meeting_skill.audio.recorder import live_record_and_transcribe
import meeting_skill.audio.recorder as recorder_module
from meeting_skill.audio.transcriber import transcribe_audio_file_result, write_segments_jsonl

DATA_CACHE = BASE_PATH / "data" / "cache"
SESSION_ROOT = DATA_CACHE / "sessions"
LEGACY_DIST_CACHE = BASE_PATH / "dist" / "data" / "cache"
DATA_CACHE.mkdir(parents=True, exist_ok=True)
SESSION_ROOT.mkdir(parents=True, exist_ok=True)
if not IS_FROZEN:
    LEGACY_DIST_CACHE.mkdir(parents=True, exist_ok=True)

last_session_dir: Path | None = None
last_wav_path: Path | None = None
last_json_path: Path | None = None
recording_thread: threading.Thread | None = None
recording_stop_event: threading.Event | None = None
transcribing = False


def run_cli_probe_if_requested() -> None:
    if "--self-test" in sys.argv:
        print(f"runtime_base={BASE_PATH}")
        print(f"config_dir={BASE_PATH / 'config'}")
        print(f"session_root={SESSION_ROOT}")
        print(f"recorder_module={getattr(recorder_module, '__file__', '<bundled>')}")
        print(f"recorder_supports_stop_event={'stop_event' in live_record_and_transcribe.__annotations__}")
        print("meeting_skill_import=ok")
        raise SystemExit(0)

    if "--transcribe-file" in sys.argv:
        index = sys.argv.index("--transcribe-file")
        try:
            wav_path = Path(sys.argv[index + 1])
        except IndexError as exc:
            raise SystemExit("--transcribe-file requires an audio path") from exc
        output_json = wav_path.with_suffix(".jsonl")
        if "--output-jsonl" in sys.argv:
            output_index = sys.argv.index("--output-jsonl")
            try:
                output_json = Path(sys.argv[output_index + 1])
            except IndexError as exc:
                raise SystemExit("--output-jsonl requires a path") from exc
        result = transcribe_audio_file_result(wav_path)
        write_segments_jsonl(result.segments, output_json)
        print(f"provider={result.provider}")
        print(f"model={result.model}")
        print(f"segments={len(result.segments)}")
        print(f"output_jsonl={output_json}")
        for item in result.diagnostics:
            print(f"diagnostic={item}")
        raise SystemExit(0)


run_cli_probe_if_requested()


def new_session_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SESSION_ROOT / stamp
    counter = 1
    while path.exists():
        path = SESSION_ROOT / f"{stamp}_{counter:02d}"
        counter += 1
    path.mkdir(parents=True, exist_ok=False)
    return path


def newest_wav_in(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = list(root.glob("*.wav")) + list(root.glob("**/*.wav"))
    return max(set(candidates), key=lambda item: item.stat().st_mtime) if candidates else None


def newest_wav() -> Path | None:
    roots = [DATA_CACHE, SESSION_ROOT]
    if not IS_FROZEN:
        roots.append(LEGACY_DIST_CACHE)
    candidates = [item for root in roots if (item := newest_wav_in(root)) is not None]
    return max(candidates, key=lambda item: item.stat().st_mtime) if candidates else None


def run_on_ui(callback: Callable[[], None]) -> None:
    if threading.current_thread() is threading.main_thread():
        callback()
    else:
        window.after(0, callback)


def append_log(text: str) -> None:
    def update() -> None:
        log_box.configure(state="normal")
        log_box.insert("end", text.rstrip() + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    run_on_ui(update)


def set_status(text: str) -> None:
    def update() -> None:
        status_var.set(text)
        window.update_idletasks()

    run_on_ui(update)


def refresh_buttons() -> None:
    is_recording = bool(recording_thread and recording_thread.is_alive())
    start_button.configure(state="disabled" if is_recording or transcribing else "normal")
    stop_button.configure(state="normal" if is_recording else "disabled")
    transcribe_button.configure(state="disabled" if is_recording or transcribing else "normal")


def set_busy_state(*, is_transcribing: bool | None = None) -> None:
    def update() -> None:
        global transcribing
        if is_transcribing is not None:
            transcribing = is_transcribing
        refresh_buttons()

    run_on_ui(update)


def start_record() -> None:
    global last_session_dir, last_wav_path, last_json_path, recording_thread, recording_stop_event
    if recording_thread and recording_thread.is_alive():
        messagebox.showwarning("Recording", "Recording is already running.")
        return

    last_session_dir = new_session_dir()
    cache_path = last_session_dir / "live_cache.jsonl"
    cache_path.touch(exist_ok=True)
    last_wav_path = None
    last_json_path = cache_path
    recording_stop_event = threading.Event()
    set_busy_state()
    set_status(f"Recording: {last_session_dir.name}")
    append_log(f"Recording started: {last_session_dir}")

    session_dir = last_session_dir
    stop_event = recording_stop_event

    def worker() -> None:
        try:
            segments = live_record_and_transcribe(
                cache_path,
                seconds=60,
                chunk_seconds=60,
                interactive=False,
                stop_event=stop_event,
            )
            recorded_wav = newest_wav_in(session_dir)

            def finish() -> None:
                global last_wav_path, last_json_path, recording_thread
                recording_thread = None
                last_wav_path = recorded_wav
                last_json_path = cache_path
                refresh_buttons()
                set_status(f"Recording saved: {session_dir}")
                append_log(f"Recording finished. Segments: {len(segments)}")
                append_log(f"Cache JSONL: {cache_path}")
                if recorded_wav:
                    append_log(f"Audio WAV: {recorded_wav}")
                else:
                    append_log("No WAV file was captured. Check microphone permissions and input device.")

            run_on_ui(finish)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

            def fail() -> None:
                global recording_thread
                recording_thread = None
                refresh_buttons()
                set_status("Recording failed")
                append_log(f"Recording failed: {error}")
                messagebox.showerror("Recording failed", error)

            run_on_ui(fail)

    recording_thread = threading.Thread(target=worker, daemon=True)
    recording_thread.start()
    refresh_buttons()
    messagebox.showinfo("Recording", f"Recording started.\nSession: {last_session_dir}\nClick Stop or wait 60 seconds.")


def stop_record() -> None:
    if recording_stop_event:
        recording_stop_event.set()
        set_status("Stopping recording...")
        append_log("Stop requested. Saving current recording...")


def trans_audio() -> None:
    global last_wav_path, last_json_path
    if recording_thread and recording_thread.is_alive():
        messagebox.showwarning("Recording", "Recording is still running. Stop it before transcription.")
        return
    if transcribing:
        messagebox.showwarning("Transcription", "Transcription is already running.")
        return

    wav_path = last_wav_path if last_wav_path and last_wav_path.exists() else newest_wav()
    if wav_path is None or not wav_path.exists():
        messagebox.showerror("Error", "No WAV file found. Please record audio first.")
        return
    output_json = wav_path.with_suffix(".jsonl")
    set_busy_state(is_transcribing=True)
    set_status(f"Transcribing: {wav_path.name}")
    append_log(f"Transcribing WAV: {wav_path}")

    def worker() -> None:
        try:
            result = transcribe_audio_file_result(wav_path)
            write_segments_jsonl(result.segments, output_json)
            diagnostics = "\n".join(result.diagnostics[-4:])

            def finish() -> None:
                global last_json_path
                last_json_path = output_json
                set_busy_state(is_transcribing=False)
                set_status(f"JSON saved: {output_json}")
                append_log(f"Transcription finished. Segments: {len(result.segments)}")
                append_log(f"Transcript JSONL: {output_json}")
                if diagnostics:
                    append_log("Diagnostics:\n" + diagnostics)
                if result.segments:
                    msg = f"Transcription finished.\nSegments: {len(result.segments)}\nJSON: {output_json}"
                else:
                    msg = f"No valid speech recognized. Empty JSON saved.\nJSON: {output_json}\n\n{diagnostics}"
                messagebox.showinfo("Done", msg)

            run_on_ui(finish)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

            def fail() -> None:
                set_busy_state(is_transcribing=False)
                set_status("Transcription failed")
                append_log(f"Transcription failed: {error}")
                messagebox.showerror("Transcription failed", error)

            run_on_ui(fail)

    threading.Thread(target=worker, daemon=True).start()


window = tk.Tk()
window.title("Meeting Speech Tool")
window.geometry("720x430")

status_var = tk.StringVar(value=f"Runtime: {BASE_PATH}")
tk.Label(window, textvariable=status_var, wraplength=680, justify="left").pack(pady=8)

button_frame = tk.Frame(window)
button_frame.pack(pady=4)
start_button = tk.Button(button_frame, text="1. Start Recording", width=22, command=start_record)
start_button.grid(row=0, column=0, padx=6)
stop_button = tk.Button(button_frame, text="Stop Recording", width=22, command=stop_record, state="disabled")
stop_button.grid(row=0, column=1, padx=6)
transcribe_button = tk.Button(button_frame, text="2. Speech To Text", width=22, command=trans_audio)
transcribe_button.grid(row=0, column=2, padx=6)

log_box = tk.Text(window, height=15, wrap="word", state="disabled")
log_box.pack(fill="both", expand=True, padx=10, pady=10)
append_log(f"Runtime directory: {BASE_PATH}")
append_log(f"Session cache directory: {SESSION_ROOT}")
append_log(f"Recorder module: {getattr(recorder_module, '__file__', '<bundled>')}")
append_log("Packaged EXE mode uses data/cache next to MeetingSpeechTool.exe.")

window.mainloop()
