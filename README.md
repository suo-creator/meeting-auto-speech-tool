# Meeting Auto Skill

This project provides a reusable Codex Skill plus a local Python workflow for meeting transcription, Markdown minutes generation, temporary meeting RAG QA, and archive export.

## Structure

```text
meeting-auto-skill/
  config/                    API and model configuration
  data/input/                Sample meeting text or audio input
  data/cache/                Runtime transcript cache
  archives/                  Timestamped meeting exports
  scripts/                   Windows/Linux launch scripts
  skills/meeting-auto-skill/ Reusable Codex Skill package
  src/meeting_skill/         Layered Python source code
```

## Windows Quick Start

```bat
.\scripts\setup.bat
.\meeting.bat run-file data\input\sample_meeting.txt --title RAG项目例会 --question "谁负责验收清单？"
```

For text or mock-mode demos, `requirements-min.txt` is enough. For microphone recording and local Whisper transcription, install the full `requirements.txt`.

## Common Commands

Run the full pipeline for a local audio or text file:

```bat
scripts\meeting.bat run-file data\input\sample_meeting.txt --title RAG项目例会 --question "谁负责验收清单？"
```

Transcribe only:

```bat
.\meeting.bat transcribe data\input\sample_meeting.txt --output-jsonl data\cache\transcript.jsonl
```

Generate minutes from transcript JSONL:

```bat
scripts\meeting.bat summarize data\cache\transcript.jsonl --output-md data\cache\minutes.md
```

Ask questions about this meeting:

```bat
scripts\meeting.bat ask data\cache\transcript.jsonl "谁负责验收清单？"
```

Record from microphone:

```bat
.\meeting.bat record --seconds 1800 --chunk-seconds 30
```

## API Configuration

Copy `config/.env.example` to `config/.env` and edit it.

```env
CHAT_PROVIDER=deepseek
CHAT_API_KEY=your_chat_model_key
CHAT_BASE_URL=https://api.deepseek.com
CHAT_MODEL=deepseek-chat
CHAT_REASONING_MODEL=deepseek-reasoner

SPEECH_PROVIDER=openai-compatible
SPEECH_BASE_URL=your_speech_model_base_url
SPEECH_API_KEY=your_speech_model_key
SPEECH_MODEL=whisper-1
```

Supported values:

- `CHAT_PROVIDER=mock|deepseek|glm`
- `SPEECH_PROVIDER=mock|whisper-local|openai-compatible`

For local Whisper, set `SPEECH_PROVIDER=whisper-local` and set `SPEECH_MODEL` to `tiny`, `base`, `small`, `medium`, or `large`.

## Output Files

Each full run creates a timestamped folder:

```text
archives/YYYYMMDD_HHMMSS_title/
  transcript.md
  transcript.jsonl
  minutes.md
  todos.csv
  qa_history.jsonl
  live_cache.jsonl
```

## Modules

- Audio layer: `src/meeting_skill/audio/` handles file transcription, microphone recording, and cache recovery.
- Model layer: `src/meeting_skill/models/` routes chat models and falls back on failure.
- Summary layer: `src/meeting_skill/text/summarizer.py` performs chunked summary and merge.
- RAG layer: `src/meeting_skill/rag/meeting_rag.py` builds a temporary TF-IDF retriever and answers with timestamp citations.
- Export layer: `src/meeting_skill/exporters/archive.py` writes transcript, minutes, todos, and QA history.

## Exception Handling

- Recording interruption: cached transcript segments remain in `live_cache.jsonl`.
- Long text: `SUMMARY_CHUNK_CHARS` controls chunked summarization before merge.
- Model failure: `ModelRouter` catches provider errors and falls back to mock output.
- Empty input: workflow raises a clear empty transcript error instead of exporting blank artifacts.
- Missing file: transcription raises `FileNotFoundError` before attempting model calls.
