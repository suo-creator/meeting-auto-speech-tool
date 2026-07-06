---
name: meeting-auto-skill
description: Automate meeting transcription, Markdown minutes generation, temporary meeting RAG QA, and archive export. Use when Codex needs to process microphone or uploaded audio/text meeting records, cache transcript segments, summarize decisions and action items, answer questions from meeting content with citations, and save reusable meeting artifacts.
---

# Meeting Auto Skill

## Workflow

1. Configure `config/.env` if real speech or chat models are required.
2. For uploaded audio or text, run `scripts/meeting.bat run-file <path> --title <meeting-title>`.
3. Add `--question "..."` to `run-file` when the one-click run should include meeting RAG QA before export.
4. For microphone capture, run `scripts/meeting.bat record --seconds 1800 --chunk-seconds 30`, then summarize and archive from the cached JSONL.
5. Use `ask` against a transcript JSONL whenever the user asks follow-up questions about this meeting.
6. Save all artifacts under `archives/<timestamp>_<title>/`.

## Commands

- `run-file`: Transcribe an audio/text file, summarize, build temporary RAG, optionally run QA, and export transcript/minutes/todos/QA history.
- `transcribe`: Convert an audio/text file into timestamped transcript JSONL.
- `record`: Capture microphone audio in chunks and append segments to cache.
- `summarize`: Generate Markdown meeting minutes from transcript JSONL.
- `ask`: Answer meeting-content questions with source time citations.
- `archive`: Export transcript and minutes into a timestamped archive folder.

## Reliability Rules

- Always preserve transcript segments to JSONL cache before summary or QA.
- If microphone recording is interrupted, continue from `live_cache.jsonl` when possible.
- If model calls fail, the router falls back to mock output so the local workflow still completes.
- For long meetings, summarize by chunks first, then merge partial summaries.
- For QA, retrieve transcript chunks first and require cited answers.
- Reject empty transcripts before export.

## Output Artifacts

- `transcript.md`: Human-readable timestamped transcript.
- `transcript.jsonl`: Structured transcript cache for recovery and RAG.
- `minutes.md`: Standard Markdown meeting minutes.
- `todos.csv`: Action item table.
- `qa_history.jsonl`: Meeting QA interactions.
