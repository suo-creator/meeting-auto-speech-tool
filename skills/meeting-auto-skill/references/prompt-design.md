# Prompt Design

Use layered prompts for meeting minutes:

1. Segment summary: extract topic, viewpoints, decisions, action items, unresolved issues from one transcript chunk.
2. Merge summary: deduplicate repeated decisions and merge action items across chunks.
3. QA answer: answer only from retrieved transcript snippets and cite snippet number plus timestamp.

For action items, require a table with `执行人`, `完成时限`, and `任务内容`. If missing, write `未明确`.
