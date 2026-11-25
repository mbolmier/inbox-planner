"""Fake LLM clients for the tests: no network, no subscription."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from inbox_planner.evaluation.labels import load_labels
from inbox_planner.llm.base import LLMRequest, LLMResponse, Usage
from inbox_planner.schemas import ExtractedItem

ZONES = ("Europe/Paris", "America/Los_Angeles")


class FakeLLM:
    """Answers with a function of the request and counts the calls."""

    name = "fake"

    def __init__(self, answer: Callable[[LLMRequest], dict[str, Any]]) -> None:
        self.answer = answer
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return LLMResponse(
            data=self.answer(request), model=request.model, usage=Usage(1000, 100), duration_ms=5
        )


def zone_of(moment: datetime) -> str:
    """The IANA zone (Paris or Oregon) whose real offset matches this moment."""
    return next(
        z for z in ZONES if moment.astimezone(ZoneInfo(z)).utcoffset() == moment.utcoffset()
    )


def as_model_item(item: ExtractedItem) -> dict[str, Any]:
    """Write a labelled item the way the model is asked to answer."""
    moment = item.starts_at or item.due_at
    assert moment is not None
    return {
        "kind": item.kind.value,
        "title": item.title,
        "local_datetime": moment.strftime("%Y-%m-%dT%H:%M"),
        "timezone": zone_of(moment),
        "duration_minutes": item.duration_minutes,
        "weekly_on": [day.value for day in item.weekly_on],
        "repeat_until": item.repeat_until.isoformat() if item.repeat_until else None,
        "location": item.location,
        "video_url": item.video_url,
        "meeting_id": item.meeting_id,
        "passcode": item.passcode,
        "priority": item.priority.value,
    }


def oracle(request: LLMRequest) -> dict[str, Any]:
    """A perfect model: it answers exactly what the labels expect."""
    task, message_id = request.tag.split("/")
    label = load_labels()[message_id]
    if task == "triage":
        return {"category": label.category.value, "reason": "oracle"}
    return {"items": [as_model_item(item) for item in label.items]}
