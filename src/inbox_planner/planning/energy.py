"""Energy of the day: how much focused work the planner may schedule."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from zoneinfo import ZoneInfo

from inbox_planner.planning.calendar import Event


class Energy(StrEnum):
    OFF = "off"
    TIRED = "tired"  # « Crevé »
    NORMAL = "normal"
    ENERGIZED = "energized"  # « En forme »


@dataclass(frozen=True)
class EnergyProfile:
    label_fr: str
    capacity_minutes: int  # personal work allowed in the day, on top of classes
    max_session_minutes: int  # longest work session without a break


PROFILES: dict[Energy, EnergyProfile] = {
    Energy.OFF: EnergyProfile("Off", 0, 0),
    Energy.TIRED: EnergyProfile("Crevé", 60, 60),
    Energy.NORMAL: EnergyProfile("Normal", 120, 120),
    Energy.ENERGIZED: EnergyProfile("En forme", 180, 120),
}

HEAVY_DAY_MINUTES = 240  # 4 h of classes and appointments in a day


def suggested_energy(day: date, events: Sequence[Event], zone: ZoneInfo) -> Energy:
    """Energy of a day until the student chooses one: fresh at the start of the week,
    tired at the end of it and on days full of classes and appointments."""
    busy = sum(
        (e.end - e.start).total_seconds() // 60
        for e in events
        if e.start.astimezone(zone).date() == day
    )
    if busy >= HEAVY_DAY_MINUTES or day.weekday() == 4:  # Friday
        return Energy.TIRED
    if day.weekday() == 0:  # Monday
        return Energy.ENERGIZED
    return Energy.NORMAL
