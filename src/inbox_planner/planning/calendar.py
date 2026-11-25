"""Turn extracted appointments into calendar events, weekly classes included.

A weekly class repeats at the same LOCAL time in its own time zone: a class at
10:00 stays at 10:00 after the clock change, even though its UTC offset moves.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from inbox_planner.schemas import ExtractedItem, ItemKind

WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
DEFAULT_EVENT_MINUTES = 60  # when the e-mail gives no duration


@dataclass(frozen=True)
class Event:
    title: str
    start: datetime
    end: datetime
    message_id: str | None = None
    location: str | None = None
    video_url: str | None = None
    meeting_id: str | None = None
    passcode: str | None = None
    weekly: bool = False


def occurrences(
    item: ExtractedItem, window_start: datetime, window_end: datetime, fallback_zone: ZoneInfo
) -> list[datetime]:
    """Start times of an appointment that overlap [window_start, window_end)."""
    first = item.starts_at
    if first is None:
        return []
    duration = timedelta(minutes=item.duration_minutes or DEFAULT_EVENT_MINUTES)
    if not item.weekly_on or item.repeat_until is None:
        return [first] if first < window_end and first + duration > window_start else []

    # Labels carry a fixed UTC offset; extracted items carry a real zone.
    zone = first.tzinfo if isinstance(first.tzinfo, ZoneInfo) else fallback_zone
    local_first = first.astimezone(zone)
    days = {day.value for day in item.weekly_on}
    day = max(local_first.date(), (window_start - duration).astimezone(zone).date())
    last: date = min(item.repeat_until, window_end.astimezone(zone).date())
    starts = []
    while day <= last:
        if WEEKDAY_CODES[day.weekday()] in days:
            moment = datetime.combine(day, local_first.time(), tzinfo=zone)
            if moment >= local_first and moment < window_end and moment + duration > window_start:
                starts.append(moment)
        day += timedelta(days=1)
    return starts


def build_events(
    items_by_message: Mapping[str, Sequence[ExtractedItem]],
    window_start: datetime,
    window_end: datetime,
    fallback_zone: ZoneInfo,
) -> list[Event]:
    """Every appointment occurrence in the window, sorted by start time."""
    events = []
    for message_id, items in items_by_message.items():
        for item in items:
            if item.kind is not ItemKind.APPOINTMENT:
                continue
            duration = timedelta(minutes=item.duration_minutes or DEFAULT_EVENT_MINUTES)
            for start in occurrences(item, window_start, window_end, fallback_zone):
                events.append(
                    Event(
                        title=item.title,
                        start=start,
                        end=start + duration,
                        message_id=message_id,
                        location=item.location,
                        video_url=item.video_url,
                        meeting_id=item.meeting_id,
                        passcode=item.passcode,
                        weekly=bool(item.weekly_on),
                    )
                )
    return sorted(events, key=lambda e: (e.start, e.title))
