from __future__ import annotations

from meeting_skill.config import get_settings
from meeting_skill.models.chat import MockChatClient, OpenAICompatibleChatClient
from meeting_skill.models.types import ChatMessage, ModelResult


class ModelRouter:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.mock = MockChatClient()
        self.chat_clients = {
            "mock": self.mock,
            "deepseek": OpenAICompatibleChatClient("deepseek", settings.chat_base_url, settings.chat_api_key),
            "glm": OpenAICompatibleChatClient("glm", settings.glm_base_url, settings.glm_api_key),
        }

    def chat(self, messages: list[ChatMessage], reasoning: bool = False, provider: str | None = None) -> ModelResult:
        selected_provider = provider or self.settings.chat_provider
        model = self.settings.chat_reasoning_model if reasoning else self.settings.chat_model
        client = self.chat_clients.get(selected_provider, self.mock)
        result = client.chat(messages, model=model, temperature=0.1 if reasoning else 0.2)
        if not result.ok:
            fallback = self.mock.chat(messages, model="mock-fallback")
            fallback.error = f"Fallback after {selected_provider} failed: {result.error}"
            return fallback
        return result
