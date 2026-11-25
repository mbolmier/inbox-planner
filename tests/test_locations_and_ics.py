from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from icalendar import Calendar

from inbox_planner.connectors.demo import DEMO_NOW, DEMO_TIMEZONES, DemoConnector
from inbox_planner.export.ics import build_calendar
from inbox_planner.llm.cache import CachedClient
from inbox_planner.locations import maps_url, resolve_place
from inbox_planner.pipeline import items_by_message, process_mailbox
from inbox_planner.planning.planner import WorkBlock

OREGON = ZoneInfo("America/Los_Angeles")
STAMP = datetime(2026, 10, 26, 15, 0, tzinfo=UTC)


def query_of(url: str) -> str:
    return parse_qs(urlsplit(url).query)["query"][0]


# --- places ----------------------------------------------------------------------


def test_a_room_opens_google_maps_in_the_right_town():
    place = resolve_place("Alder Hall 120", None, area="Corvallis, OR")

    assert place is not None and not place.online
    assert place.url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert query_of(place.url) == "Alder Hall 120, Corvallis, OR"


def test_the_town_is_not_added_twice():
    address = "418 SW Quillback Way, Corvallis, OR 97333"

    assert query_of(maps_url(address, "Corvallis, OR")) == address


def test_video_links_name_their_provider_and_keep_id_and_code():
    zoom = resolve_place(None, "https://zoom.us/j/93184402716?pwd=abc", "931 8440 2716", "482913")
    meet = resolve_place(None, "https://meet.google.com/xpr-qwmn-fkd")

    assert zoom is not None and (zoom.label, zoom.meeting_id, zoom.passcode) == (
        "Zoom",
        "931 8440 2716",
        "482913",
    )
    assert meet is not None and meet.label == "Google Meet"


def test_a_wrapped_teams_link_is_unwrapped():
    wrapped = (
        "https://eur03.safelinks.protection.outlook.com/?url=https%3A%2F%2Fteams.microsoft.com"
        "%2Fl%2Fmeetup-join%2Fabc&data=05"
    )

    place = resolve_place(None, wrapped)

    assert place is not None
    assert (place.label, place.url) == (
        "Microsoft Teams",
        "https://teams.microsoft.com/l/meetup-join/abc",
    )


def test_a_javascript_link_is_never_made_clickable():
    place = resolve_place("Room 12", "javascript:alert(document.cookie)")

    assert place is not None and not place.online  # falls back to the physical place
    assert resolve_place(None, "javascript:alert(1)") is None


# --- .ics export -------------------------------------------------------------------


# What the app really exports: the pipeline's output, replayed from the recordings.
PROCESSED = process_mailbox(DemoConnector(), CachedClient(), DEMO_TIMEZONES, now=DEMO_NOW)
ITEMS = items_by_message(PROCESSED)
MESSAGES = {p.message.id: p.message for p in PROCESSED}


def demo_calendar(blocks=()) -> Calendar:
    raw = build_calendar(ITEMS, MESSAGES, OREGON, {"osu": "Corvallis, OR"}, blocks, STAMP)
    return Calendar.from_ical(raw)


def events_of(calendar: Calendar) -> dict[str, object]:
    return {str(e["uid"]): e for e in calendar.walk("VEVENT")}


def test_weekly_class_is_one_recurring_event_in_its_time_zone():
    [lecture] = [
        e
        for uid, e in events_of(demo_calendar()).items()
        if uid.startswith("m04-") and e["rrule"]["BYDAY"] == ["MO", "WE", "FR"]
    ]

    start = lecture.decoded("dtstart")
    assert start.tzinfo.key == "America/Los_Angeles"  # a TZID, not a fixed offset
    assert (start.hour, start.minute) == (10, 0)
    rule = lecture["rrule"]
    assert rule["FREQ"] == ["WEEKLY"] and rule["BYDAY"] == ["MO", "WE", "FR"]
    assert rule["UNTIL"][0].tzinfo is not None  # UNTIL is in UTC, as RFC 5545 requires


def test_the_file_carries_the_definition_of_its_time_zones():
    zones = {str(tz["tzid"]) for tz in demo_calendar().walk("VTIMEZONE")}

    assert {"America/Los_Angeles", "Europe/Paris"} <= zones


def test_a_deadline_ends_at_its_due_time_with_a_reminder_the_day_before():
    hw4 = events_of(demo_calendar())["m08-0@inbox-planner"]

    assert str(hw4["summary"]).startswith("Échéance : ")
    assert hw4.decoded("dtend") == datetime.fromisoformat("2026-11-01T23:59:00-08:00")
    [alarm] = hw4.walk("VALARM")
    assert alarm.decoded("trigger") == timedelta(days=-1)


def test_video_meetings_carry_the_unwrapped_link_and_the_codes():
    tutor = events_of(demo_calendar())["m18-0@inbox-planner"]

    assert str(tutor["url"]).startswith("https://teams.microsoft.com/")
    assert "348 712 905 166" in str(tutor["description"])
    assert str(tutor["location"]) == "Microsoft Teams"


def test_uids_are_unique_and_stable_between_exports():
    first, second = events_of(demo_calendar()), events_of(demo_calendar())

    assert first.keys() == second.keys()
    assert len(first) == sum(len(items) for items in ITEMS.values())


def test_planned_work_blocks_can_be_added_and_do_not_block_the_agenda():
    start = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)
    block = WorkBlock("m09-0", "ST 411 proposal", start, start + timedelta(minutes=60))

    work = events_of(demo_calendar([block]))["work-m09-0-20261027T1500Z@inbox-planner"]

    assert str(work["summary"]) == "Travail : ST 411 proposal"
    assert str(work["transp"]) == "TRANSPARENT"
    assert work.decoded("dtstart").date() == date(2026, 10, 27)
