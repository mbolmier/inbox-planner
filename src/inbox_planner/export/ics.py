"""Export to an .ics file (RFC 5545), for Apple Calendar and Google Calendar.

- Appointments keep their time zone (TZID + VTIMEZONE). A weekly class becomes
  one event with an RRULE in that zone, so it stays at 10:00 after the clock
  change instead of moving to 9:00.
- A deadline becomes a short event ending at the due time, with a reminder the
  day before.
- Planned work blocks can be added.
- UIDs are stable: importing the file again updates events, it does not
  duplicate them.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from icalendar import Alarm, Calendar
from icalendar import Event as IcsEvent

from inbox_planner.locations import resolve_place
from inbox_planner.mail.models import Message
from inbox_planner.planning.calendar import DEFAULT_EVENT_MINUTES
from inbox_planner.planning.planner import WorkBlock
from inbox_planner.schemas import ExtractedItem, ItemKind

DEADLINE_EVENT_MINUTES = 15


def _in_zone(moment: datetime, fallback_zone: ZoneInfo) -> datetime:
    """Give the datetime a real IANA zone, so that the file carries a TZID."""
    if isinstance(moment.tzinfo, ZoneInfo):
        return moment
    return moment.astimezone(fallback_zone)


def _source(message: Message | None) -> str:
    if message is None:
        return ""
    return f"Source : mail « {message.subject} » de {message.sender}."


def build_calendar(
    items_by_message: Mapping[str, Sequence[ExtractedItem]],
    messages: Mapping[str, Message],
    fallback_zone: ZoneInfo,
    areas: Mapping[str, str] | None = None,
    blocks: Sequence[WorkBlock] = (),
    stamp: datetime | None = None,
) -> bytes:
    stamp = stamp or datetime.now(UTC)
    calendar = Calendar()
    calendar.add("prodid", "-//inbox-planner//FR")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", "inbox-planner")

    for message_id, items in items_by_message.items():
        message = messages.get(message_id)
        area = (areas or {}).get(message.mailbox) if message else None
        for n, item in enumerate(items):
            event = IcsEvent()
            event.add("uid", f"{message_id}-{n}@inbox-planner")
            event.add("dtstamp", stamp)
            description = [_source(message)]

            if item.kind is ItemKind.APPOINTMENT and item.starts_at is not None:
                start = _in_zone(item.starts_at, fallback_zone)
                minutes = item.duration_minutes or DEFAULT_EVENT_MINUTES
                event.add("summary", item.title)
                event.add("dtstart", start)
                event.add("dtend", start + timedelta(minutes=minutes))
                if item.weekly_on and item.repeat_until:
                    last = datetime.combine(
                        item.repeat_until, time(23, 59, 59), tzinfo=start.tzinfo
                    )
                    event.add(
                        "rrule",
                        {
                            "freq": "weekly",
                            "byday": [day.value for day in item.weekly_on],
                            "until": last.astimezone(UTC),  # RFC 5545: UNTIL in UTC with TZID
                        },
                    )
                place = resolve_place(
                    item.location, item.video_url, item.meeting_id, item.passcode, area
                )
                if place and place.online:
                    event.add("location", place.label)
                    event.add("url", place.url)
                    if place.meeting_id:
                        description.append(f"ID de réunion : {place.meeting_id}")
                    if place.passcode:
                        description.append(f"Code : {place.passcode}")
                elif place:
                    event.add("location", place.label)
                    description.append(f"Plan : {place.url}")
            elif item.due_at is not None:
                due = _in_zone(item.due_at, fallback_zone)
                event.add("summary", f"Échéance : {item.title}")
                event.add("dtstart", due - timedelta(minutes=DEADLINE_EVENT_MINUTES))
                event.add("dtend", due)
                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("description", f"Demain : {item.title}")
                alarm.add("trigger", timedelta(days=-1))
                event.add_component(alarm)
            else:
                continue
            event.add("description", "\n".join(line for line in description if line))
            calendar.add_component(event)

    for block in blocks:
        event = IcsEvent()
        event.add("uid", f"work-{block.task_id}-{block.start:%Y%m%dT%H%MZ}@inbox-planner")
        event.add("dtstamp", stamp)
        event.add("summary", f"Travail : {block.title}")
        event.add("dtstart", block.start.astimezone(fallback_zone))
        event.add("dtend", block.end.astimezone(fallback_zone))
        event.add("transp", "TRANSPARENT")  # planned work does not make you look busy
        calendar.add_component(event)

    calendar.add_missing_timezones()
    return calendar.to_ical()
