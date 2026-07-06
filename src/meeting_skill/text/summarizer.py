from __future__ import annotations

from meeting_skill.config import get_settings
from meeting_skill.models.router import ModelRouter
from meeting_skill.models.types import ChatMessage, TranscriptSegment

MINUTES_PROMPT = """
你是企业会议纪要专家。请基于会议转写原文生成 Markdown 标准会议纪要。
必须包含以下层级：
1. 会议核心主题
2. 各方观点
3. 达成共识与最终决策
4. 待执行任务：用 Markdown 表格输出，列为 执行人、完成时限、任务内容
5. 遗留未解决问题
要求：只根据原文总结；不确定的信息写“未明确”；不要编造人名、日期或决策。
""".strip()


def transcript_to_text(segments: list[TranscriptSegment]) -> str:
    return "\n".join(segment.to_markdown() for segment in segments)


def split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        cut = text.rfind("\n", start, end)
        if cut <= start:
            cut = end
        chunks.append(text[start:cut].strip())
        start = cut
    return [chunk for chunk in chunks if chunk]


class MinutesEngine:
    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()
        self.settings = get_settings()

    def summarize(self, segments: list[TranscriptSegment]) -> str:
        transcript = transcript_to_text(segments)
        chunks = split_long_text(transcript, self.settings.summary_chunk_chars)
        partials = []
        for idx, chunk in enumerate(chunks):
            prompt = f"{MINUTES_PROMPT}\n\n这是第 {idx + 1}/{len(chunks)} 段会议原文：\n{chunk}"
            result = self.router.chat([ChatMessage("system", MINUTES_PROMPT), ChatMessage("user", prompt)], reasoning=True)
            partials.append(result.content)
        if len(partials) == 1:
            return partials[0]
        merge_prompt = "\n\n".join(partials)
        result = self.router.chat(
            [
                ChatMessage("system", MINUTES_PROMPT),
                ChatMessage("user", f"请合并以下分段纪要，去重、保留冲突与未决事项，输出最终 Markdown：\n{merge_prompt}"),
            ],
            reasoning=True,
        )
        return result.content
