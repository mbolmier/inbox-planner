from datetime import timedelta

import pytest
from fakes import FakeLLM

from inbox_planner.agents.context import render_message
from inbox_planner.agents.extraction import ExtractionAgent, ModelItem, to_extracted_item
from inbox_planner.agents.triage import TriageAgent
from inbox_planner.connectors.demo import DEMO_TIMEZONES, DemoConnector
from inbox_planner.llm.base import LLMError
from inbox_planner.schemas import Category

MESSAGES = {m.id: m for m in DemoConnector().fetch_messages()}
SAFE_LINK = (
    "https://eur03.safelinks.protection.outlook.com/?url=https%3A%2F%2Fteams.microsoft.com"
    "%2Fl%2Fmeetup-join%2F19%253ameeting_abc%2540thread.v2%2F0&data=05&reserved=0"
)


def model_item(**overrides) -> ModelItem:
    fields = {
        "kind": "deadline",
        "title": "x",
        "local_datetime": "2026-11-05T12:00",
        "timezone": "America/Los_Angeles",
        "duration_minutes": None,
        "weekly_on": [],
        "repeat_until": None,
        "location": None,
        "video_url": None,
        "meeting_id": None,
        "passcode": None,
        "priority": "medium",
    }
    return ModelItem.model_validate(fields | overrides)


def test_prompt_gives_the_sending_weekday_and_the_mailbox_time_zone():
    prompt = render_message(MESSAGES["m12"], DEMO_TIMEZONES)

    assert "Sent: Friday 2026-10-23 10:15 (America/Los_Angeles, UTC-07:00)" in prompt
    assert "Mailbox: osu (default time zone: America/Los_Angeles)" in prompt


@pytest.mark.parametrize(
    ("local", "zone", "offset_hours"),
    [
        ("2026-10-29T14:00", "America/Los_Angeles", -7),  # before the US clock change
        ("2026-11-05T12:00", "America/Los_Angeles", -8),  # after it
        ("2026-11-01T23:59", "America/Los_Angeles", -8),  # on the day of the change
        ("2026-10-24T18:00", "Europe/Paris", 2),  # before the European clock change
        ("2026-10-31T23:59", "Europe/Paris", 1),  # after it
    ],
)
def test_code_computes_the_utc_offset_from_local_time_and_zone(local, zone, offset_hours):
    item = to_extracted_item(model_item(local_datetime=local, timezone=zone))

    assert item.due_at is not None
    assert item.due_at.utcoffset() == timedelta(hours=offset_hours)


def test_safe_links_are_unwrapped_in_code():
    item = to_extracted_item(model_item(kind="appointment", video_url=SAFE_LINK))

    assert (
        item.video_url == "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc%40thread.v2/0"
    )


def test_a_deadline_never_keeps_a_weekly_recurrence():
    item = to_extracted_item(model_item(weekly_on=["MO"], repeat_until="2026-12-04"))

    assert item.weekly_on == () and item.repeat_until is None


@pytest.mark.parametrize(
    "bad",
    [{"timezone": "Paris time"}, {"local_datetime": "next Friday"}, {"title": ""}],
)
def test_impossible_items_are_rejected(bad):
    with pytest.raises(ValueError):
        to_extracted_item(model_item(**bad))


def test_extraction_agent_drops_invalid_items_and_counts_them():
    good = model_item().model_dump(mode="json")
    bad = model_item(timezone="Mars/Olympus").model_dump(mode="json")
    agent = ExtractionAgent(FakeLLM(lambda r: {"items": [good, bad]}), "m", DEMO_TIMEZONES)

    result = agent.run(MESSAGES["m09"])

    assert len(result.items) == 1
    assert result.invalid_items == 1


def test_triage_agent_returns_the_category_and_tags_the_request():
    llm = FakeLLM(lambda r: {"category": "noise", "reason": "promotion"})

    result = TriageAgent(llm, "claude-haiku-5-5", DEMO_TIMEZONES).run(MESSAGES["m01"])

    assert result.category is Category.NOISE
    assert llm.calls[0].tag == "triage/m01"
    assert llm.calls[0].model == "claude-haiku-5-5"


def test_an_answer_outside_the_schema_is_an_llm_error():
    llm = FakeLLM(lambda r: {"category": "urgent"})

    with pytest.raises(LLMError):
        TriageAgent(llm, "m", DEMO_TIMEZONES).run(MESSAGES["m01"])
