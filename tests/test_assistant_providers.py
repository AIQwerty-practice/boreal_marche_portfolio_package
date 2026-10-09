from __future__ import annotations

import json

import httpx
from pydantic import SecretStr

from boreal_marche.assistant.providers import (
    HostedChatProvider,
    HostedProviderConfig,
    HuggingFaceChatProvider,
    OllamaChatProvider,
    OllamaProviderConfig,
    OpenAIChatProvider,
    ProviderRequest,
    configured_providers,
)

REQUEST = ProviderRequest(system_prompt="Return JSON.", user_prompt="Route this request.")


def test_hosted_adapter_contract_and_cost() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"intent":"policy_search"}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    provider = HostedChatProvider(
        HostedProviderConfig(
            base_url="https://provider.example/v1",
            api_key=SecretStr("secret"),
            model="hosted-test",
            input_cost_per_million_tokens=1.0,
            output_cost_per_million_tokens=2.0,
        ),
        transport=httpx.MockTransport(handler),
    )
    result = provider.generate(REQUEST)
    assert result.provider == "hosted"
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.estimated_cost_usd == 0.00014


def test_ollama_adapter_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        assert request.headers["authorization"] == "Bearer internal-token"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["think"] is False
        assert body["format"] == "json"
        return httpx.Response(
            200,
            json={
                "message": {"content": '{"intent":"recommendation"}'},
                "prompt_eval_count": 80,
                "eval_count": 12,
            },
        )

    provider = OllamaChatProvider(
        OllamaProviderConfig(
            base_url="http://ollama.internal:11434",
            model="local-test",
            bearer_token=SecretStr("internal-token"),
        ),
        transport=httpx.MockTransport(handler),
    )
    result = provider.generate(REQUEST)
    assert result.provider == "ollama"
    assert result.estimated_cost_usd == 0.0
    assert result.input_tokens == 80


def test_unconfigured_providers_are_skipped(monkeypatch) -> None:
    for name in (
        "HOSTED_LLM_BASE_URL",
        "HOSTED_LLM_API_KEY",
        "HOSTED_LLM_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "BOREAL_ENABLE_OPENAI",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "BOREAL_ENABLE_HUGGINGFACE",
        "HF_TOKEN",
        "HF_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    assert configured_providers() == {}


def test_openai_provider_needs_explicit_enablement(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")
    monkeypatch.delenv("BOREAL_ENABLE_OPENAI", raising=False)
    assert OpenAIChatProvider.from_environment() is None
    monkeypatch.setenv("BOREAL_ENABLE_OPENAI", "1")
    provider = OpenAIChatProvider.from_environment()
    assert provider is not None
    assert provider.name == "openai"
    assert provider.config.base_url == "https://api.openai.com/v1"


def test_openai_adapter_targets_official_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"intent":"product_lookup","refused":false}'}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )

    provider = OpenAIChatProvider(
        HostedProviderConfig(
            base_url="https://api.openai.com/v1",
            api_key=SecretStr("test-only"),
            model="test-model",
        ),
        transport=httpx.MockTransport(handler),
    )
    assert provider.generate(REQUEST).provider == "openai"


def test_huggingface_provider_is_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "test-only")
    monkeypatch.setenv("HF_MODEL", "Qwen/test-model")
    monkeypatch.delenv("BOREAL_ENABLE_HUGGINGFACE", raising=False)
    assert HuggingFaceChatProvider.from_environment() is None
    monkeypatch.setenv("BOREAL_ENABLE_HUGGINGFACE", "1")
    provider = HuggingFaceChatProvider.from_environment()
    assert provider is not None
    assert provider.config.base_url == "https://router.huggingface.co/v1"
    assert provider.model == "Qwen/test-model"


def test_huggingface_adapter_uses_inference_router() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://router.huggingface.co/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"intent":"policy_search"}'}}]})

    provider = HuggingFaceChatProvider(
        HostedProviderConfig(
            base_url="https://router.huggingface.co/v1",
            api_key=SecretStr("test-only"),
            model="test-model",
        ),
        transport=httpx.MockTransport(handler),
    )
    assert provider.generate(REQUEST).provider == "huggingface"
