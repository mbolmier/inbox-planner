"""What the pipeline extracts from an e-mail.

The hand-made labels of the evaluation use exactly these models, so the
evaluation compares objects of the same shape.
"""

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Category(StrEnum):
    """Triage result: the main reason the e-mail matters, or not."""

    APPOINTMENT = "appointment"  # be somewhere, or online, at a given time
    DEADLINE = "deadline"  # some work must be handed in before a due time
    PROCEDURE = "procedure"  # an administrative process to complete
    INFO = "info"  # worth knowing, nothing to schedule
    NOISE = "noise"  # marketing, newsletters, social notifications, phishing


class ItemKind(StrEnum):
    APPOINTMENT = "appointment"
    DEADLINE = "deadline"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Weekday(StrEnum):
    MO = "MO"
    TU = "TU"
    WE = "WE"
    TH = "TH"
    FR = "FR"
    SA = "SA"
    SU = "SU"


class ExtractedItem(BaseModel):
    """One thing to put in the calendar or in the to-do list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ItemKind
    title: str = Field(min_length=1)
    starts_at: AwareDatetime | None = None  # appointment start, first occurrence if weekly
    due_at: AwareDatetime | None = None  # deadline: the instant it is due
    duration_minutes: int | None = Field(default=None, gt=0)
    weekly_on: tuple[Weekday, ...] = ()  # recurring classes, e.g. ("MO", "WE", "FR")
    repeat_until: date | None = None  # last day of the recurrence, inclusive
    location: str | None = None  # physical place, used for the map link
    video_url: str | None = None  # real meeting URL, Outlook Safe Links unwrapped
    meeting_id: str | None = None
    passcode: str | None = None
    priority: Priority = Priority.MEDIUM

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.kind is ItemKind.APPOINTMENT:
            if self.starts_at is None or self.due_at is not None:
                raise ValueError("an appointment has starts_at and no due_at")
        elif self.due_at is None or self.starts_at is not None or self.weekly_on:
            raise ValueError("a deadline has due_at, no starts_at and no recurrence")
        if bool(self.weekly_on) != (self.repeat_until is not None):
            raise ValueError("weekly_on and repeat_until go together")
        return self
