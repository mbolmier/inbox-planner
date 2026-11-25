"""LLM client that runs the local Claude Code CLI in headless mode (`claude -p`).

It uses the Claude subscription the CLI is logged in with, so it costs nothing
beyond that subscription. It is used to record answers locally; the demo, the
tests and the CI replay those recordings instead (see cache.py).

Each call is isolated: an empty temporary folder (no project CLAUDE.md), Claude
Code's system prompt replaced by ours, every tool disabled, no MCP server, no
saved session. API keys are removed from the environment so that the call can
never be billed to an API account.
"""

import json
import os
import subprocess
import tempfile
from typing import Any

from inbox_planner.llm.base import (
    LLMError,
    LLMRefusal,
    LLMRequest,
    LLMResponse,
    LLMUnavailable,
    Usage,
)

_BILLED_CREDENTIALS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class ClaudeCodeClient:
    name = "claude-code"

    def __init__(self, executable: str = "claude", timeout_s: float = 300) -> None:
        self.executable = executable
        self.timeout_s = timeout_s

    def build_command(self, request: LLMRequest) -> list[str]:
        return [
            self.executable,
            "--print",
            "--model",
            request.model,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(request.json_schema()),
            "--system-prompt",
            request.system,
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]

    def complete(self, request: LLMRequest) -> LLMResponse:
        with tempfile.TemporaryDirectory(prefix="inbox-planner-llm-") as empty_dir:
            try:
                process = subprocess.run(
                    self.build_command(request),
                    input=request.prompt,
                    capture_output=True,
                    text=True,
                    cwd=empty_dir,
                    env=subscription_only_env(),
                    timeout=self.timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise LLMUnavailable(
                    f"claude CLI timed out after {self.timeout_s:.0f} s"
                ) from error
        try:
            envelope = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            # Only the exit code is reported: stderr could echo the prompt.
            raise LLMUnavailable(
                f"claude CLI returned no JSON (exit code {process.returncode})"
            ) from error
        return parse_envelope(envelope)


def subscription_only_env() -> dict[str, str]:
    """The current environment without any credential that would bill an API account."""
    return {k: v for k, v in os.environ.items() if k not in _BILLED_CREDENTIALS}


def parse_envelope(envelope: dict[str, Any]) -> LLMResponse:
    """Turn the CLI's JSON result into an LLMResponse."""
    if envelope.get("is_error"):
        raise LLMUnavailable(f"claude CLI error: {str(envelope.get('result', ''))[:200]}")
    if envelope.get("stop_reason") == "refusal":
        raise LLMRefusal("the model declined to answer")

    data = envelope.get("structured_output")
    if data is None:
        try:
            data = json.loads(envelope.get("result") or "")
        except json.JSONDecodeError as error:
            raise LLMError("the model answer is not valid JSON") from error
    if not isinstance(data, dict):
        raise LLMError("the model answer is not a JSON object")

    usage = envelope.get("usage") or {}
    input_tokens = sum(
        int(usage.get(key) or 0)
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    model_usage = envelope.get("modelUsage") or {}
    return LLMResponse(
        data=data,
        model=next(iter(model_usage), "unknown"),
        usage=Usage(input_tokens, int(usage.get("output_tokens") or 0)),
        duration_ms=int(envelope.get("duration_ms") or 0),
    )
