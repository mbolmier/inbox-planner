"""The contract every LLM client follows, and the objects it exchanges."""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class LLMError(Exception):
    """The model could not produce a usable answer."""


class CacheMiss(LLMError):
    """Replay mode found no recorded answer for this exact request."""


class LLMUnavailable(LLMError):
    """The model could not be reached at all (not logged in, timeout...): stop the run."""


class LLMRefusal(LLMError):
    """The model declined to answer."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0  # includes tokens read from or written to the prompt cache
    output_tokens: int = 0  # includes thinking tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens
        )


@dataclass(frozen=True)
class LLMRequest:
    """One structured-output call: a system prompt, a user prompt and a JSON schema."""

    model: str
    system: str
    prompt: str
    schema: type[BaseModel]
    tag: str = ""  # e.g. "triage/m02": helps a human read the cache, never contains mail text

    def json_schema(self) -> dict[str, Any]:
        return self.schema.model_json_schema()

    def cache_key(self) -> str:
        """Fingerprint of everything that can change the answer."""
        payload = json.dumps(
            {
                "model": self.model,
                "system": self.system,
                "prompt": self.prompt,
                "schema": self.json_schema(),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LLMResponse:
    data: dict[str, Any]  # the JSON object returned by the model
    model: str  # the model that actually answered
    usage: Usage = field(default_factory=Usage)
    duration_ms: int = 0
    from_cache: bool = False


@runtime_checkable
class LLMClient(Protocol):
    name: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the model's JSON answer for this request."""
        ...
