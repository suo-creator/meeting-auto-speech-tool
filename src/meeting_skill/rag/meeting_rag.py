from __future__ import annotations

import re
from dataclasses import dataclass

from meeting_skill.config import get_settings
from meeting_skill.models.router import ModelRouter
from meeting_skill.models.types import ChatMessage, TranscriptSegment
from meeting_skill.text.summarizer import transcript_to_text


@dataclass
class RagChunk:
    chunk_id: str
    text: str
    source: str
    start: float
    end: float


def chunk_transcript(segments: list[TranscriptSegment]) -> list[RagChunk]:
    settings = get_settings()
    chunks: list[RagChunk] = []
    current: list[TranscriptSegment] = []
    current_len = 0
    for segment in segments:
        rendered = segment.to_markdown()
        if current and current_len + len(rendered) > settings.rag_chunk_chars:
            chunks.append(_make_chunk(len(chunks), current))
            overlap_text = transcript_to_text(current)[-settings.rag_chunk_overlap :]
            current = [TranscriptSegment(current[-1].start, current[-1].end, current[-1].speaker, overlap_text)]
            current_len = len(overlap_text)
        current.append(segment)
        current_len += len(rendered)
    if current:
        chunks.append(_make_chunk(len(chunks), current))
    return chunks


def _make_chunk(index: int, segments: list[TranscriptSegment]) -> RagChunk:
    return RagChunk(
        chunk_id=f"meeting-chunk-{index:04d}",
        text=transcript_to_text(segments),
        source=f"{segments[0].start:0.1f}s-{segments[-1].end:0.1f}s",
        start=segments[0].start,
        end=segments[-1].end,
    )


class TemporaryMeetingRag:
    def __init__(self, segments: list[TranscriptSegment], router: ModelRouter | None = None) -> None:
        self.chunks = chunk_transcript(segments)
        self.router = router or ModelRouter()
        self.history: list[ChatMessage] = []
        self._fit_index()

    def _fit_index(self) -> None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", ngram_range=(1, 2))
            self.matrix = self.vectorizer.fit_transform([chunk.text for chunk in self.chunks]) if self.chunks else None
        except Exception:
            self.vectorizer = None
            self.matrix = None

    def retrieve(self, question: str, top_k: int | None = None) -> list[RagChunk]:
        if not self.chunks:
            return []
        top_k = top_k or get_settings().rag_top_k
        if self.vectorizer is not None and self.matrix is not None:
            from sklearn.metrics.pairwise import cosine_similarity

            query = self.vectorizer.transform([question])
            scores = cosine_similarity(query, self.matrix).ravel()
            ranked = scores.argsort()[::-1][:top_k]
            return [self.chunks[int(i)] for i in ranked if scores[int(i)] > 0 or len(self.chunks) <= top_k]
        terms = [term for term in re.split(r"\W+", question) if term]
        scored = [(sum(chunk.text.count(term) for term in terms), chunk) for chunk in self.chunks]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def ask(self, question: str) -> dict[str, object]:
        hits = self.retrieve(question)
        context = "\n\n".join(f"[{idx + 1}] {chunk.source} {chunk.chunk_id}\n{chunk.text}" for idx, chunk in enumerate(hits))
        prompt = f"""
你是会议内容答疑 Agent。只基于检索到的会议原文片段回答问题；如果原文没有依据，回答“会议原文未明确”。
回答必须包含：直接回答、依据片段编号、原文出处时间。

问题：{question}

检索片段：
{context}
""".strip()
        messages = [ChatMessage("system", "你必须避免幻觉，必须引用会议原文时间。"), *self.history, ChatMessage("user", prompt)]
        result = self.router.chat(messages, reasoning=True)
        self.history.extend([ChatMessage("user", question), ChatMessage("assistant", result.content)])
        return {
            "question": question,
            "answer": result.content,
            "citations": [{"chunk_id": chunk.chunk_id, "source": chunk.source, "preview": chunk.text[:240]} for chunk in hits],
        }
