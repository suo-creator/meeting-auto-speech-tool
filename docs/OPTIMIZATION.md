# 可量化优化说明

## 1. 长文本总结效率

- 分块参数：`SUMMARY_CHUNK_CHARS=7000`，避免单次 Prompt 超上下文。
- 两阶段总结：先对每段生成局部纪要，再合并去重，复杂度约为 `O(n chunks)`。
- 可量化指标：
  - `summary_chunks = ceil(transcript_chars / SUMMARY_CHUNK_CHARS)`
  - `avg_summary_latency = total_summary_seconds / summary_chunks`
  - `compression_ratio = minutes_chars / transcript_chars`
- 建议目标：纪要压缩比控制在 5%-15%，单块总结失败率低于 1%。

## 2. 问答检索准确率

- 当前轻量实现：TF-IDF ngram 检索，无需 Chroma/FAISS 等中间件。
- 分块参数：`RAG_CHUNK_CHARS=900`，`RAG_CHUNK_OVERLAP=120`。
- 可量化指标：
  - `citation_hit_rate = cited_answers / total_answers`
  - `top_k_recall = questions_with_relevant_chunk_in_top_k / total_questions`
  - `unsupported_answer_rate = answers_without_source / total_answers`
- 建议目标：引用覆盖率大于 95%，无出处回答率小于 3%。

## 3. 进一步优化方案

- 引入语义 embedding：将 TF-IDF 替换为 bge-small-zh 或企业内网 embedding 服务。
- 引入说话人识别：音频层接入 pyannote 或语音模型 diarization 能力。
- 引入术语表：在 Prompt 中注入项目名、部门名、人名映射，提高纪要一致性。
- 引入增量索引：长会议实时转写时，每 5-10 个片段更新一次临时索引，支持边开会边问答。
- 引入评测集：维护 30-100 个会议问题，统计 top-k recall、引用覆盖率、回答人工通过率。
