import json
from types import SimpleNamespace

import pytest
from fakes import FakeLLM
from pydantic import BaseModel

from inbox_planner.llm.anthropic_api import AnthropicClient
from inbox_planner.llm.base import CacheMiss, LLMRefusal, LLMRequest, LLMUnavailable
from inbox_planner.llm.cache import CachedClient
from inbox_planner.llm.claude_code import ClaudeCodeClient, parse_envelope, subscription_only_env


class Answer(BaseModel):
    category: str


def request(prompt: str = "Secret mail text", model: str = "claude-haiku-5-5") -> LLMRequest:
    return LLMRequest(model=model, system="sys", prompt=prompt, schema=Answer, tag="triage/m01")


# --- cache -------------------------------------------------------------------


def test_cache_records_once_then_replays(tmp_path):
    live = FakeLLM(lambda r: {"category": "noise"})
    recorder = CachedClient(tmp_path, live=live)

    first = recorder.complete(request())
    replayed = CachedClient(tmp_path).complete(request())

    assert len(live.calls) == 1
    assert not first.from_cache and replayed.from_cache
    assert replayed.data == {"category": "noise"}
    assert replayed.usage == first.usage


def test_recorded_file_never_contains_the_prompt(tmp_path):
    CachedClient(tmp_path, live=FakeLLM(lambda r: {"category": "noise"})).complete(request())

    [stored] = tmp_path.rglob("*.json")
    assert "Secret mail text" not in stored.read_text(encoding="utf-8")


def test_replay_fails_loudly_when_the_prompt_changed(tmp_path):
    CachedClient(tmp_path, live=FakeLLM(lambda r: {"category": "noise"})).complete(request())

    with pytest.raises(CacheMiss):
        CachedClient(tmp_path).complete(request(prompt="Edited prompt"))


# --- Claude Code CLI ------------------------------------------------------------


def test_cli_call_is_isolated_and_structured():
    command = ClaudeCodeClient().build_command(request())

    assert command[:2] == ["claude", "--print"]
    assert command[command.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in command and "--no-session-persistence" in command
    assert json.loads(command[command.index("--json-schema") + 1])["required"] == ["category"]


def test_cli_environment_holds_no_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "not-real")

    env = subscription_only_env()

    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env


def test_cli_envelope_with_structured_output():
    response = parse_envelope(
        {
            "is_error": False,
            "structured_output": {"category": "info"},
            "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 7},
            "modelUsage": {"claude-haiku-5-5": {}},
            "duration_ms": 1234,
        }
    )

    assert response.data == {"category": "info"}
    assert response.model == "claude-haiku-5-5"
    assert (response.usage.input_tokens, response.usage.output_tokens) == (100, 7)


def test_cli_envelope_with_json_text_result():
    response = parse_envelope({"result": '{"category": "noise"}', "usage": {}})

    assert response.data == {"category": "noise"}


def test_cli_error_and_refusal():
    with pytest.raises(LLMUnavailable):
        parse_envelope({"is_error": True, "result": "Failed to authenticate"})
    with pytest.raises(LLMRefusal):
        parse_envelope({"stop_reason": "refusal", "result": ""})


# --- Anthropic API (fake SDK client: the real API is never called) ---------------


class FakeSDK:
    def __init__(self, stop_reason: str = "end_turn") -> None:
        self.arguments: dict = {}
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, **arguments):
        self.arguments = arguments
        usage = SimpleNamespace(
            input_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=10,
            output_tokens=3,
        )
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            parsed_output=Answer(category="deadline"),
            usage=usage,
            model=arguments["model"],
        )


def test_api_client_sends_the_schema_and_reads_the_parsed_output():
    sdk = FakeSDK()

    response = AnthropicClient(sdk).complete(request(model="claude-sonnet-5-5"))

    assert sdk.arguments["output_format"] is Answer
    assert sdk.arguments["system"] == "sys"
    assert response.data == {"category": "deadline"}
    assert response.usage.input_tokens == 15


def test_api_client_enables_server_side_fallback_except_on_haiku():
    sonnet, haiku = FakeSDK(), FakeSDK()

    AnthropicClient(sonnet).complete(request(model="claude-sonnet-5-5"))
    AnthropicClient(haiku).complete(request(model="claude-haiku-5-5"))

    assert sonnet.arguments["fallbacks"] == "default"
    assert sonnet.arguments["betas"] == ["server-side-fallback-2026-07-01"]
    assert "fallbacks" not in haiku.arguments


def test_api_client_reports_a_refusal():
    with pytest.raises(LLMRefusal):
        AnthropicClient(FakeSDK(stop_reason="refusal")).complete(request())
