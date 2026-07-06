from __future__ import annotations

import requests

from meeting_skill.models.types import ChatMessage, ModelResult


class ChatClient:
    def chat(self, messages: list[ChatMessage], model: str, temperature: float = 0.2) -> ModelResult:
        raise NotImplementedError


class MockChatClient(ChatClient):
    provider = "mock"

    def chat(self, messages: list[ChatMessage], model: str, temperature: float = 0.2) -> ModelResult:
        prompt = messages[-1].content if messages else ""
        if "会议内容答疑 Agent" in prompt or "检索片段" in prompt:
            if "资源排期" in prompt:
                content = "直接回答：资源排期尚未完全确认，需要会后和运维团队继续沟通。\n依据片段编号：[1]\n原文出处时间：0.0s-48.0s"
            elif "决策" in prompt or "最终" in prompt:
                content = "直接回答：会议决定先采用轻量化本地部署，后续再接入企业统一模型网关。\n依据片段编号：[1]\n原文出处时间：0.0s-48.0s"
            elif "验收清单" in prompt:
                content = "直接回答：李四负责整理验收清单，并计划下周一交付。\n依据片段编号：[1]\n原文出处时间：0.0s-48.0s"
            else:
                content = "直接回答：会议原文未明确。\n依据片段编号：[1]\n原文出处时间：0.0s-48.0s"
        elif "会议纪要" in prompt or "Markdown" in prompt:
            content = """# 会议纪要\n\n## 1. 会议核心主题\n- 本次会议围绕示例转写内容展开。\n\n## 2. 各方观点\n- 张三：提出项目进度与交付风险。\n- 李四：关注客户验收与后续跟进。\n\n## 3. 达成共识与最终决策\n- 按既定里程碑推进，并强化风险同步。\n\n## 4. 待执行任务\n| 执行人 | 完成时限 | 任务内容 |\n| --- | --- | --- |\n| 张三 | 本周五 | 整理项目风险清单 |\n| 李四 | 下周一 | 对接客户验收反馈 |\n\n## 5. 遗留未解决问题\n- 资源排期仍需进一步确认。\n"""
        else:
            content = f"基于会议原文的本地 mock 回答：{prompt[:300]}"
        return ModelResult(content=content, provider=self.provider, model=model)


class OpenAICompatibleChatClient(ChatClient):
    def __init__(self, provider: str, base_url: str, api_key: str) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def chat(self, messages: list[ChatMessage], model: str, temperature: float = 0.2) -> ModelResult:
        if not self.api_key:
            return ModelResult("", self.provider, model, ok=False, error="API key is empty")
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": temperature,
                    "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                },
                timeout=90,
            )
            response.raise_for_status()
            data = response.json()
            return ModelResult(data["choices"][0]["message"]["content"], self.provider, model)
        except Exception as exc:  # noqa: BLE001
            return ModelResult("", self.provider, model, ok=False, error=str(exc))
