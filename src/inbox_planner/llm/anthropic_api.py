"""LLM client for the Anthropic API, through the official Python SDK.

For anyone who has an API key (`uv sync --extra anthropic`, then ANTHROPIC_API_KEY).
It is NOT executed in this project, which spends nothing beyond a Claude
subscription: it follows the SDK documentation, its calls were checked against
the installed SDK's method signatures, and it is tested with a fake SDK client.
"""

import time
from typing import Any

from inbox_planner.llm.base import LLMError, LLMRefusal, LLMRequest, LLMResponse, Usage

# Server-side fallback: if the model declines, the API re-runs the same request
# on another model inside the same call. Haiku models have no such fallback.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_NO_FALLBACK_PREFIXES = ("claude-haiku-",)


class AnthropicClient:
    name = "anthropic-api"

    def __init__(self, sdk_client: Any | None = None, max_tokens: int = 16000) -> None:
        if sdk_client is None:
            try:
                import anthropic
            except ImportError as error:
                raise LLMError("the Anthropic SDK is missing: uv sync --extra anthropic") from error
            sdk_client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        self._sdk = sdk_client
        self.max_tokens = max_tokens

    def complete(self, request: LLMRequest) -> LLMResponse:
        arguments: dict[str, Any] = {
            "model": request.model,
            "max_tokens": self.max_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.prompt}],
            "output_format": request.schema,
        }
        if not request.model.startswith(_NO_FALLBACK_PREFIXES):
            arguments |= {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

        started = time.monotonic()
        response = self._sdk.beta.messages.parse(**arguments)
        if response.stop_reason == "refusal":
            raise LLMRefusal("the model declined to answer")
        if response.stop_reason == "max_tokens":
            raise LLMError("the answer was cut off by max_tokens")
        if response.parsed_output is None:
            raise LLMError("the answer has no structured output")

        usage = response.usage
        input_tokens = (
            usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0)
        )
        return LLMResponse(
            data=response.parsed_output.model_dump(mode="json"),
            model=response.model,
            usage=Usage(input_tokens, usage.output_tokens),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
