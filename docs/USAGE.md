# Usage Guide

## 1. Initialize Environment

```bat
.\scripts\setup.bat
```

For a lightweight text-only demo, you can install the smaller dependency set manually:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-min.txt
set PYTHONPATH=%cd%\src
python -m meeting_skill.cli --help
```

Use `requirements.txt` for microphone recording and local Whisper transcription.

## 2. One-Click File Workflow

```bat
.\meeting.bat run-file data\input\sample_meeting.txt --title 项目例会 --question "谁负责验收清单？"
```

Audio files use the same command:

```bat
scripts\meeting.bat run-file data\input\meeting.wav --title 客户评审会 --question "会议最终决策是什么？"
```

This runs transcription, transcript cache writing, minutes generation, temporary RAG build, optional QA, and archive export.

## 3. Microphone Recording

```bat
.\meeting.bat record --seconds 3600 --chunk-seconds 30
```

The recorder writes transcript segments to cache. If recording is interrupted, already flushed segments remain available.

## 4. Meeting QA

```bat
scripts\meeting.bat ask data\cache\transcript.jsonl "会议最终决策是什么？"
```

The answer includes retrieved transcript snippets and timestamp ranges.

## 5. Reuse As A Codex Skill

Copy `skills/meeting-auto-skill` into your Codex skills directory. The reusable workflow is:

`record/file transcription -> JSONL cache -> layered minutes -> temporary RAG -> QA -> archive export`.
