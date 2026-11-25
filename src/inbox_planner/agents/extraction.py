"""Extraction agent: turn one e-mail into calendar entries and to-do items.

The model reads; the code computes. The model returns a local wall-clock time
and an IANA time zone name; Python's zoneinfo computes the exact UTC offset,
clock changes included. Outlook Safe Links are unwrapped in code too.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from inbox_planner.agents.context import render_message
from inbox_planner.llm.base import LLMClient, LLMError, LLMRequest, Usage
from inbox_planner.mail.links import unwrap_safelinks
from inbox_planner.mail.models import Message
from inbox_planner.schemas import ExtractedItem, ItemKind, Priority, Weekday

SYSTEM_PROMPT = """\
You extract calendar entries and to-do items from one e-mail received by a university \
student on exchange abroad. Return every item the student must put in a calendar \
(appointment) or a to-do list (deadline). Return an empty list when there is none.

For each item:
- kind: "appointment" if the student must attend at a given time; "deadline" if something \
must be handed in or done before a due time.
- local_datetime: the start of an appointment or the due time of a deadline, as the local \
wall-clock time "YYYY-MM-DDTHH:MM". Never convert between time zones yourself.
- timezone: the IANA time zone of that local time. A time given without a zone is in the \
sender's time zone, which is the mailbox default unless the e-mail says otherwise \
("heure de Paris" means Europe/Paris; flight times are local to each airport).
- A deadline without a time is due at 23:59.
- Resolve relative dates ("this Monday", "tomorrow") from the date the e-mail was sent.
- Judge time only against the reference time given above the e-mail, never \
against any other date you may know.
- duration_minutes: only if the e-mail gives it (a duration, an end time, a time limit); \
otherwise null.
- Weekly classes: one item whose local_datetime is the first session, with weekly_on \
(MO, TU, WE, TH, FR, SA, SU) and repeat_until (YYYY-MM-DD, last day included). For any \
other item, weekly_on is empty and repeat_until is null.
- location: the physical place as written (room, address, airport); null if online or unknown.
- video_url: the meeting link exactly as written; meeting_id and passcode exactly as written.
- priority: high for exams, major graded work, job interviews and administrative steps \
with consequences; low for optional or personal plans; medium otherwise.

Create no item for promotions, newsletters, optional events announced to everyone, drop-in \
office hours, or notices that need no action. When a session is moved, return only the \
new slot."""


class ModelItem(BaseModel):
    """One item as the model returns it, before the code computes the offset."""

    model_config = ConfigDict(extra="forbid")

    kind: ItemKind
    title: str
    local_datetime: str = Field(description="Local wall-clock time, YYYY-MM-DDTHH:MM.")
    timezone: str = Field(description="IANA time zone, e.g. Europe/Paris.")
    duration_minutes: int | None
    weekly_on: list[Weekday]
    repeat_until: str | None = Field(description="YYYY-MM-DD, or null.")
    location: str | None
    video_url: str | None
    meeting_id: str | None
    passcode: str | None
    priority: Priority


class ModelExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ModelItem]


def to_extracted_item(item: ModelItem) -> ExtractedItem:
    """Compute the exact instant from local time + zone. Raises ValueError if invalid."""
    try:
        zone = ZoneInfo(item.timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"unknown time zone {item.timezone!r}") from error
    local = datetime.fromisoformat(item.local_datetime).replace(tzinfo=None)
    instant = local.replace(tzinfo=zone)

    is_appointment = item.kind is ItemKind.APPOINTMENT
    weekly = tuple(item.weekly_on) if is_appointment else ()
    try:
        return ExtractedItem(
            kind=item.kind,
            title=item.title,
            starts_at=instant if is_appointment else None,
            due_at=None if is_appointment else instant,
            duration_minutes=item.duration_minutes,
            weekly_on=weekly,
            repeat_until=date.fromisoformat(item.repeat_until)
            if weekly and item.repeat_until
            else None,
            location=item.location or None,
            video_url=unwrap_safelinks(item.video_url) if item.video_url else None,
            meeting_id=item.meeting_id or None,
            passcode=item.passcode or None,
            priority=item.priority,
        )
    except ValidationError as error:
        raise ValueError(str(error)) from error


@dataclass(frozen=True)
class ExtractionResult:
    message_id: str
    items: tuple[ExtractedItem, ...]
    invalid_items: int  # returned by the model but impossible to convert
    model: str
    usage: Usage
    duration_ms: int


class ExtractionAgent:
    def __init__(
        self,
        llm: LLMClient,
        model: str,
        timezones: Mapping[str, str],
        now: datetime | None,
    ) -> None:
        self.llm = llm
        self.model = model
        self.timezones = timezones
        self.now = now  # reference time: frozen in the demo, None = each e-mail's arrival

    def run(self, message: Message) -> ExtractionResult:
        request = LLMRequest(
            model=self.model,
            system=SYSTEM_PROMPT,
            prompt=render_message(message, self.timezones, self.now),
            schema=ModelExtraction,
            tag=f"extraction/{message.id}",
        )
        response = self.llm.complete(request)
        try:
            output = ModelExtraction.model_validate(response.data)
        except ValidationError as error:
            raise LLMError(
                f"extraction answer for {message.id} does not match the schema"
            ) from error

        items: list[ExtractedItem] = []
        invalid = 0
        for raw_item in output.items:
            try:
                items.append(to_extracted_item(raw_item))
            except ValueError:
                invalid += 1
        return ExtractionResult(
            message_id=message.id,
            items=tuple(items),
            invalid_items=invalid,
            model=response.model,
            usage=response.usage,
            duration_ms=response.duration_ms,
        )
