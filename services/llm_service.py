from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from models.schemas import Settings
from utils.retry import resilient
from utils.validators import clean_text


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str: ...


class ChatCompletionsProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str, settings: Settings, extra_headers: dict[str, str] | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.settings = settings
        self.extra_headers = extra_headers or {}

    @resilient(attempts=3, initial=1, maximum=20, retry_exceptions=(httpx.HTTPError,))
    async def complete(self, system: str, user: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.settings.yaml_config.llm.temperature,
            "max_tokens": self.settings.yaml_config.llm.max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", **self.extra_headers}
        async with httpx.AsyncClient(timeout=self.settings.yaml_config.llm.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return clean_text(data["choices"][0]["message"]["content"])


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, settings: Settings) -> None:
        self.api_key = api_key
        self.model = model
        self.settings = settings

    @resilient(attempts=3, initial=1, maximum=20, retry_exceptions=(httpx.HTTPError,))
    async def complete(self, system: str, user: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.settings.yaml_config.llm.max_tokens,
            "temperature": self.settings.yaml_config.llm.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.yaml_config.llm.timeout_seconds) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return clean_text(" ".join(part.get("text", "") for part in data.get("content", [])))


class MockProvider(LLMProvider):
    async def complete(self, system: str, user: str) -> str:
        if "comment" in user.lower() or "post:" in user.lower():
            return "This is a practical perspective, especially the way it connects the idea to real execution. Thanks for sharing it."
        return "Hi, I noticed your work and would be glad to connect and follow your updates."


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = self._build_provider()

    def _build_provider(self) -> LLMProvider:
        provider = self.settings.llm_provider.lower()
        if provider == "mock":
            return MockProvider()
        if provider == "openrouter":
            if not self.settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY is required")
            return ChatCompletionsProvider(
                api_key=self.settings.openrouter_api_key,
                model=self.settings.openrouter_model,
                base_url="https://openrouter.ai/api/v1",
                settings=self.settings,
                extra_headers={"HTTP-Referer": "http://localhost", "X-Title": "LinkedIn Outreach Automation"},
            )
        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required")
            return ChatCompletionsProvider(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                base_url="https://api.openai.com/v1",
                settings=self.settings,
            )
        if provider == "anthropic":
            if not self.settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is required")
            return AnthropicProvider(self.settings.anthropic_api_key, self.settings.anthropic_model, self.settings)
        raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def complete(self, system: str, user: str) -> str:
        return await self.provider.complete(system, user)
