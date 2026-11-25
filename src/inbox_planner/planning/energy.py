"""Energy of the day: how much focused work the planner may schedule."""

from dataclasses import dataclass
from enum import StrEnum


class Energy(StrEnum):
    OFF = "off"
    TIRED = "tired"  # « Crevé »
    NORMAL = "normal"
    ENERGIZED = "energized"  # « En forme »


@dataclass(frozen=True)
class EnergyProfile:
    label_fr: str
    capacity_minutes: int  # focused work allowed in the day
    max_block_minutes: int  # longest work block without a break


PROFILES: dict[Energy, EnergyProfile] = {
    Energy.OFF: EnergyProfile("Off", 0, 0),
    Energy.TIRED: EnergyProfile("Crevé", 120, 45),
    Energy.NORMAL: EnergyProfile("Normal", 240, 90),
    Energy.ENERGIZED: EnergyProfile("En forme", 360, 120),
}
