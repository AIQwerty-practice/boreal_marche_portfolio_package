"""Configuration-driven hosted and Ollama provider adapters for Head C evaluation."""

from __future__ import annotations

import os
import ssl
import time
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderRequest(StrictModel):
    system_prompt: str = Field(min_length=1, max_length=10_000)
    user_prompt: str = Field(min_length=1, max_length=2_000)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=200, ge=1, le=2_000)


class ProviderResponse(StrictModel):
    provider: str
    model: str
    text: str
    latency_ms: float = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class AssistantProvider(Protocol):
    name: str
    model: str

    def generate(self, request: ProviderRequest) -> ProviderResponse: ...


@dataclass(frozen=True)
class HostedProviderConfig:
    base_url: str
    api_key: SecretStr
    model: str
    input_cost_per_million_tokens: float | None = None
    output_cost_per_million_tokens: float | None = None
    timeout_seconds: float = 60.0

    @classmethod
    def from_environment(cls) -> HostedProviderConfig | None:
        base_url = os.getenv("HOSTED_LLM_BASE_URL")
        api_key = os.getenv("HOSTED_LLM_API_KEY")
        model = os.getenv("HOSTED_LLM_MODEL")
        if not all((base_url, api_key, model)):
            return None
        return cls(
            base_url=base_url,
            api_key=SecretStr(api_key),
            model=model,
            input_cost_per_million_tokens=_optional_float("HOSTED_LLM_INPUT_COST_PER_MILLION"),
            output_cost_per_million_tokens=_optional_float("HOSTED_LLM_OUTPUT_COST_PER_MILLION"),
        )


@dataclass(frozen=True)
class OllamaProviderConfig:
    base_url: str
    model: str
    bearer_token: SecretStr | None = None
    timeout_seconds: float = 120.0

    @classmethod
    def from_environment(cls) -> OllamaProviderConfig | None:
        base_url = os.getenv("OLLAMA_BASE_URL")
        model = os.getenv("OLLAMA_MODEL")
        if not all((base_url, model)):
            return None
        token = os.getenv("OLLAMA_BEARER_TOKEN")
        return cls(
            base_url=base_url,
            model=model,
            bearer_token=SecretStr(token) if token else None,
        )


def _optional_float(name: str) -> float | None:
    value = os.getenv(name)
    return float(value) if value else None


class HostedChatProvider:
    """Adapter for a hosted service exposing an OpenAI-compatible chat endpoint."""

    name = "hosted"

    def __init__(self, config: HostedProviderConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.model = config.model
        self.client = httpx.Client(
            timeout=config.timeout_seconds,
            transport=transport,
            headers={"Authorization": f"Bearer {config.api_key.get_secret_value()}"},
            verify=ssl.create_default_context(),
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        started = time.perf_counter()
        response = self.client.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        return ProviderResponse(
            provider=self.name,
            model=self.model,
            text=payload["choices"][0]["message"]["content"],
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self._estimated_cost(input_tokens, output_tokens),
        )

    def _estimated_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if (
            input_tokens is None
            or output_tokens is None
            or self.config.input_cost_per_million_tokens is None
            or self.config.output_cost_per_million_tokens is None
        ):
            return None
        return (
            input_tokens * self.config.input_cost_per_million_tokens
            + output_tokens * self.config.output_cost_per_million_tokens
        ) / 1_000_000


class OpenAIChatProvider(HostedChatProvider):
    """OpenAI-only hosted routing provider; model and key are server-side settings."""

    name = "openai"

    @classmethod
    def from_environment(cls) -> OpenAIChatProvider | None:
        key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL")
        if os.getenv("BOREAL_ENABLE_OPENAI") != "1" or not key or not model:
            return None
        return cls(
            HostedProviderConfig(
                base_url="https://api.openai.com/v1",
                api_key=SecretStr(key),
                model=model,
                input_cost_per_million_tokens=_optional_float("OPENAI_INPUT_COST_PER_MILLION"),
                output_cost_per_million_tokens=_optional_float("OPENAI_OUTPUT_COST_PER_MILLION"),
            )
        )


class HuggingFaceChatProvider(HostedChatProvider):
    """Opt-in Hugging Face Inference Providers routing through its chat endpoint."""

    name = "huggingface"

    @classmethod
    def from_environment(cls) -> HuggingFaceChatProvider | None:
        key = os.getenv("HF_TOKEN")
        model = os.getenv("HF_MODEL")
        if os.getenv("BOREAL_ENABLE_HUGGINGFACE") != "1" or not key or not model:
            return None
        return cls(
            HostedProviderConfig(
                base_url="https://router.huggingface.co/v1",
                api_key=SecretStr(key),
                model=model,
                input_cost_per_million_tokens=_optional_float("HF_INPUT_COST_PER_MILLION"),
                output_cost_per_million_tokens=_optional_float("HF_OUTPUT_COST_PER_MILLION"),
            )
        )


class OllamaChatProvider:
    """Adapter for an Ollama server, intended to run privately in AWS."""

    name = "ollama"

    def __init__(self, config: OllamaProviderConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.model = config.model
        headers = {}
        if config.bearer_token:
            headers["Authorization"] = f"Bearer {config.bearer_token.get_secret_value()}"
        self.client = httpx.Client(
            timeout=config.timeout_seconds,
            transport=transport,
            headers=headers,
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        started = time.perf_counter()
        response = self.client.post(
            f"{self.config.base_url.rstrip('/')}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                "stream": False,
                "think": False,
                "format": "json",
                "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
            },
        )
        response.raise_for_status()
        payload = response.json()
        return ProviderResponse(
            provider=self.name,
            model=self.model,
            text=payload["message"]["content"],
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=payload.get("prompt_eval_count"),
            output_tokens=payload.get("eval_count"),
            estimated_cost_usd=0.0,
        )


def configured_providers() -> dict[str, AssistantProvider]:
    providers: dict[str, AssistantProvider] = {}
    hosted = HostedProviderConfig.from_environment()
    ollama = OllamaProviderConfig.from_environment()
    if hosted:
        providers["hosted"] = HostedChatProvider(hosted)
    openai = OpenAIChatProvider.from_environment()
    if openai:
        providers["openai"] = openai
    huggingface = HuggingFaceChatProvider.from_environment()
    if huggingface:
        providers["huggingface"] = huggingface
    if ollama:
        providers["ollama"] = OllamaChatProvider(ollama)
    return providers
