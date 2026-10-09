"""One fictional, non-customer Head C routing check against private Ollama."""

from __future__ import annotations

import argparse
import json

import httpx

from boreal_marche.assistant.provider_evaluation import parse_provider_decision
from boreal_marche.assistant.providers import (
    OllamaChatProvider,
    OllamaProviderConfig,
    ProviderRequest,
)
from boreal_marche.assistant.routing_prompt import SYSTEM_PROMPT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 600:
        parser.error("--timeout must be between 0 and 600 seconds")

    config = OllamaProviderConfig.from_environment()
    if config is None:
        print(json.dumps({"ready": False, "reason": "Ollama is not configured"}))
        return 2

    provider = OllamaChatProvider(
        OllamaProviderConfig(
            base_url=config.base_url,
            model=config.model,
            bearer_token=config.bearer_token,
            timeout_seconds=args.timeout,
        )
    )
    try:
        result = provider.generate(
            ProviderRequest(
                system_prompt=SYSTEM_PROMPT,
                user_prompt="What is the return policy for an unopened item?",
                max_tokens=80,
            )
        )
        decision = parse_provider_decision(result.text)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        # Never print the raw provider response, request, credentials, or private URLs.
        print(json.dumps({"ready": False, "model": config.model, "error_type": type(exc).__name__}))
        return 1

    ready = decision.intent == "policy_search" and not decision.refused
    print(
        json.dumps(
            {
                "ready": ready,
                "provider": result.provider,
                "model": result.model,
                "intent": decision.intent,
                "refused": decision.refused,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": round(result.latency_ms),
                "fictional_case": True,
            }
        )
    )
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
