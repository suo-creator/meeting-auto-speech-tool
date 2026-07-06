# Runtime Troubleshooting

## Recommended Windows Commands

From the project root, use:

```bat
.\meeting.bat doctor
.\meeting.bat transcribe data\cache\your_audio.wav --output-jsonl data\cache\your_audio.jsonl --debug
.\meeting.bat record --seconds 60 --chunk-seconds 15
```

From `data/cache`, use:

```bat
..\..\meeting.bat doctor
..\..\meeting.bat transcribe your_audio.wav --output-jsonl your_audio.jsonl --debug
```

PowerShell does not run batch files from the current folder by bare name. Use `.\meeting.bat` in project root or `..\..\meeting.bat` from `data/cache`.

## Desktop EXE Build

Build the one-file desktop program from the project root:

```bat
.\scripts\build_desktop.bat
```

The distributable runtime layout is:

```text
dist/
  MeetingSpeechTool.exe
  config/.env
  config/.env.example
  data/cache/sessions/
```

In one-file PyInstaller mode the program is temporarily extracted under `_MEI...`, but runtime files are no longer read from that temp folder. `MEETING_SKILL_ROOT` is set to the folder beside `MeetingSpeechTool.exe`, so config, recordings, and transcript JSONL files are stored under `dist/config` and `dist/data/cache/sessions`.

The EXE imports the bundled `meeting_skill` package directly. It does not call `src/meeting_skill/audio/recorder.py` as an external script, so the external `src` folder is not required after packaging.

## Recording And Transcription Files

Each GUI recording creates a new timestamped session folder:

```text
data/cache/sessions/YYYYMMDD_HHMMSS/
  live_chunk_0000.wav
  live_cache.jsonl
  live_chunk_0000.jsonl
```

`live_cache.jsonl` is created at recording start, even if no speech is recognized. When the `Speech To Text` button runs, the transcript JSONL is written next to the WAV file. Repeated recordings do not overwrite earlier sessions.

Path lookup accepts either an explicit path or only a file name. If only `live_chunk_0000.wav` is passed, the CLI searches project cache folders, session folders, and legacy `dist/data/cache` folders, then uses the newest matching file.

## Checks

- `doctor` prints the loaded `.env` path and whether it exists.
- Local Whisper runs inside `.venv`; direct system Python may miss `requests`, `torch`, or `whisper`.
- `imageio-ffmpeg` is used automatically, so system PATH does not need ffmpeg.
- Remote `127.0.0.1` transcription is retried three times. `stream disconnected` means the local service closed the connection or does not support the endpoint.

## Visible Config

The real config is `config/.env`, which Windows may hide. Use:

```bat
config\show_env.bat
```

A visible template is also available at `config/env.local.example`.
