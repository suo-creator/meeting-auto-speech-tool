from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from meeting_skill.config import project_path
from meeting_skill.models.types import TranscriptSegment
from meeting_skill.text.summarizer import transcript_to_text


def create_archive_dir(meeting_title: str | None = None) -> Path:
    safe_title = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", meeting_title or "meeting").strip("_")
    folder = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{safe_title}"
    path = project_path("archives", folder)
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_transcript(segments: list[TranscriptSegment], archive_dir: Path) -> dict[str, Path]:
    md_path = archive_dir / "transcript.md"
    jsonl_path = archive_dir / "transcript.jsonl"
    md_path.write_text("# 原始完整转写文本\n\n" + transcript_to_text(segments) + "\n", encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as file:
        for segment in segments:
            file.write(json.dumps(segment.to_dict(), ensure_ascii=False) + "\n")
    return {"transcript_md": md_path, "transcript_jsonl": jsonl_path}


def export_minutes(minutes: str, archive_dir: Path) -> Path:
    path = archive_dir / "minutes.md"
    path.write_text(minutes, encoding="utf-8")
    return path


def export_todos(minutes: str, archive_dir: Path) -> Path:
    path = archive_dir / "todos.csv"
    rows = []
    for line in minutes.splitlines():
        if "|" not in line or "---" in line or "执行人" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 3:
            rows.append(cells[:3])
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["执行人", "完成时限", "任务内容"])
        writer.writerows(rows)
    return path


def export_qa_history(history: list[dict[str, object]], archive_dir: Path) -> Path:
    path = archive_dir / "qa_history.jsonl"
    with path.open("w", encoding="utf-8") as file:
        for item in history:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
    return path
