"""Consistency checks on the hand-made labels: they catch annotation mistakes."""

from collections import Counter
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pytest

from inbox_planner.connectors.demo import DemoConnector
from inbox_planner.evaluation.labels import load_labels
from inbox_planner.schemas import Category, ExtractedItem, ItemKind

ZONES = (ZoneInfo("Europe/Paris"), ZoneInfo("America/Los_Angeles"))
WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
VIDEO_HOSTS = {"zoom.us", "teams.microsoft.com", "meet.google.com"}

MESSAGES = {m.id: m for m in DemoConnector().fetch_messages()}
LABELS = load_labels()
ITEMS = [
    pytest.param(label.message, item, id=f"{label.message}-{n}")
    for label in LABELS.values()
    for n, item in enumerate(label.items)
]
RECURRING_ITEMS = [p for p in ITEMS if p.values[1].weekly_on]
VIDEO_ITEMS = [p for p in ITEMS if p.values[1].video_url]


def instant(item: ExtractedItem) -> datetime:
    when = item.starts_at or item.due_at
    assert when is not None
    return when


def has_a_real_local_offset(dt: datetime) -> bool:
    """True if the UTC offset is the one Paris or Oregon really had at that instant."""
    return any(dt.utcoffset() == dt.astimezone(zone).utcoffset() for zone in ZONES)


def test_every_message_has_exactly_one_label():
    assert set(LABELS) == set(MESSAGES)


def test_forty_messages_and_every_category_is_well_represented():
    counts = Counter(label.category for label in LABELS.values())

    assert len(MESSAGES) == 40
    assert all(counts[category] >= 5 for category in Category), counts


def test_items_match_the_category():
    for label in LABELS.values():
        kinds = {item.kind for item in label.items}
        if label.category in (Category.NOISE, Category.INFO):
            assert not label.items, label.message
        elif label.category is Category.APPOINTMENT:
            assert ItemKind.APPOINTMENT in kinds, label.message
        else:
            assert ItemKind.DEADLINE in kinds, label.message


@pytest.mark.parametrize(("message_id", "item"), ITEMS)
def test_item_happens_after_the_message_was_sent(message_id: str, item: ExtractedItem):
    assert instant(item) > MESSAGES[message_id].sent_at


def test_every_offset_matches_the_real_clock_in_paris_or_oregon():
    # Catches a summer-time offset written after the clock change, or the reverse.
    dates = [m.sent_at for m in MESSAGES.values()]
    dates += [instant(item.values[1]) for item in ITEMS]

    assert [d.isoformat() for d in dates if not has_a_real_local_offset(d)] == []


@pytest.mark.parametrize(("message_id", "item"), RECURRING_ITEMS)
def test_recurring_item_starts_on_one_of_its_weekdays(message_id: str, item: ExtractedItem):
    assert item.starts_at is not None and item.repeat_until is not None
    assert WEEKDAY_CODES[item.starts_at.weekday()] in item.weekly_on
    assert item.repeat_until >= item.starts_at.date()


@pytest.mark.parametrize(("message_id", "item"), VIDEO_ITEMS)
def test_video_link_is_the_unwrapped_meeting_url(message_id: str, item: ExtractedItem):
    assert item.video_url is not None
    assert urlsplit(item.video_url).hostname in VIDEO_HOSTS
