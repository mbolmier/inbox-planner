"""Deterministic planner: earliest deadline first, spread over the days.

Tasks are taken by due date (then priority). Their work is spread out: each
block goes to the day before the deadline that can take the longest block, then
to the day with the most work capacity left, then to the earliest day. Blocks are never
longer than the day's energy allows, never over an appointment, never beyond
the day's work capacity. Times are computed in UTC and only shown in local time.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from inbox_planner.planning.calendar import Event
from inbox_planner.planning.energy import PROFILES, Energy, EnergyProfile
from inbox_planner.schemas import ExtractedItem, ItemKind, Priority

PRIORITY_RANK = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
Interval = tuple[datetime, datetime]  # [start, end) in UTC


@dataclass(frozen=True)
class PlannerSettings:
    day_start: time = time(8, 0)
    day_end: time = time(22, 0)
    gap_minutes: int = 15  # around appointments and between work blocks
    min_block_minutes: int = 25  # no smaller block, unless less than that is left
    default_task_minutes: int = 60  # when the e-mail gives no work estimate
    horizon_days: int = 7


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    due_at: datetime
    minutes: int
    priority: Priority = Priority.MEDIUM
    message_id: str | None = None


@dataclass(frozen=True)
class WorkBlock:
    task_id: str
    title: str
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class Shortfall:
    """Work that could not be placed before the deadline."""

    task: Task
    missing_minutes: int
    reason: str


@dataclass(frozen=True)
class Plan:
    start: datetime
    zone: ZoneInfo
    energy_by_day: dict[date, Energy]
    events: tuple[Event, ...]
    blocks: tuple[WorkBlock, ...]
    at_risk: tuple[Shortfall, ...]  # deadline inside the horizon, not enough time
    later: tuple[Shortfall, ...] = field(default=())  # deadline after the horizon
    conflicts: tuple[tuple[Event, Event], ...] = field(default=())  # overlapping appointments


def tasks_from_items(
    items_by_message: Mapping[str, Sequence[ExtractedItem]],
    settings: PlannerSettings = PlannerSettings(),
) -> list[Task]:
    """One task per extracted deadline; unknown work time gets the default estimate."""
    tasks = []
    for message_id, items in items_by_message.items():
        for n, item in enumerate(items):
            if item.kind is ItemKind.DEADLINE and item.due_at is not None:
                tasks.append(
                    Task(
                        id=f"{message_id}-{n}",
                        title=item.title,
                        due_at=item.due_at,
                        minutes=item.duration_minutes or settings.default_task_minutes,
                        priority=item.priority,
                        message_id=message_id,
                    )
                )
    return tasks


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def _ceil_to_five_minutes(moment: datetime) -> datetime:
    moment = moment.astimezone(UTC).replace(second=0, microsecond=0)
    return moment + timedelta(minutes=-moment.minute % 5)


def _block_length(remaining: int, limit: int, min_block: int) -> int:
    """Length of the next block, or 0 if this slot should be skipped.

    Never leaves a crumb: if the leftover would be shorter than a minimum block,
    the block either takes everything or stops early enough to leave one.
    """
    length = min(remaining, limit)
    if length < min(min_block, remaining):
        return 0
    leftover = remaining - length
    if 0 < leftover < min_block:
        length = remaining - min_block
        if length < min_block:
            return 0
    return length


def _best_fit(
    slots: Sequence[Interval],
    remaining: int,
    room: int,
    profile: EnergyProfile,
    due: datetime,
    settings: PlannerSettings,
) -> tuple[int, int] | None:
    """Slot of a day that takes the longest block (the earliest on a tie), so that a
    task is not cut into pieces when one free slot can hold it: (slot index, length)."""
    best: tuple[int, int] | None = None
    for i, (start, end) in enumerate(slots):
        limit = min(profile.max_block_minutes, room, _minutes(min(end, due) - start))
        length = _block_length(remaining, limit, settings.min_block_minutes)
        if length > 0 and (best is None or length > best[1]):
            best = (i, length)
    return best


def find_conflicts(events: Sequence[Event]) -> list[tuple[Event, Event]]:
    """Pairs of appointments that overlap: the student has to choose."""
    ordered = sorted(events, key=lambda e: e.start)
    conflicts = []
    for n, first in enumerate(ordered):
        for second in ordered[n + 1 :]:
            if second.start >= first.end:
                break
            conflicts.append((first, second))
    return conflicts


def _subtract(intervals: list[Interval], cut: Interval) -> list[Interval]:
    result = []
    for start, end in intervals:
        if cut[1] <= start or cut[0] >= end:
            result.append((start, end))
            continue
        if start < cut[0]:
            result.append((start, cut[0]))
        if cut[1] < end:
            result.append((cut[1], end))
    return result


def free_intervals(
    day: date,
    zone: ZoneInfo,
    not_before: datetime,
    events: Sequence[Event],
    settings: PlannerSettings,
) -> list[Interval]:
    """Free time of one day, in UTC: the working window minus appointments and margins."""
    opens = datetime.combine(day, settings.day_start, tzinfo=zone).astimezone(UTC)
    closes = datetime.combine(day, settings.day_end, tzinfo=zone).astimezone(UTC)
    opens = max(opens, _ceil_to_five_minutes(not_before))
    intervals: list[Interval] = [(opens, closes)] if opens < closes else []
    gap = timedelta(minutes=settings.gap_minutes)
    for event in events:
        intervals = _subtract(
            intervals, (event.start.astimezone(UTC) - gap, event.end.astimezone(UTC) + gap)
        )
    return intervals


def plan_week(
    tasks: Sequence[Task],
    events: Sequence[Event],
    now: datetime,
    zone: ZoneInfo,
    energy_by_day: Mapping[date, Energy] | None = None,
    settings: PlannerSettings = PlannerSettings(),
) -> Plan:
    """Place the tasks in the free time of the next days. Same input, same plan."""
    first_day = now.astimezone(zone).date()
    days = [first_day + timedelta(days=n) for n in range(settings.horizon_days)]
    energy = {day: (energy_by_day or {}).get(day, Energy.NORMAL) for day in days}
    horizon_end = datetime.combine(days[-1] + timedelta(days=1), time(0), tzinfo=zone)
    gap = timedelta(minutes=settings.gap_minutes)

    free = {day: free_intervals(day, zone, now, events, settings) for day in days}
    used = dict.fromkeys(days, 0)
    blocks: list[WorkBlock] = []
    at_risk: list[Shortfall] = []
    later: list[Shortfall] = []

    for task in sorted(tasks, key=lambda t: (t.due_at, PRIORITY_RANK[t.priority], t.id)):
        due = task.due_at.astimezone(UTC)
        if due <= now:
            at_risk.append(Shortfall(task, task.minutes, "échéance déjà passée"))
            continue
        remaining = task.minutes
        while remaining > 0:
            # The next block goes to the day that can take the longest block (so a task
            # is not cut into pieces for nothing), then to the day with the most
            # capacity left, then to the earliest day. The work is spread over the days
            # before the deadline instead of piling up at the start of the week.
            best: tuple[tuple[int, int], date, int, int] | None = None
            for day in days:
                profile = PROFILES[energy[day]]
                room = profile.capacity_minutes - used[day]
                if room <= 0:
                    continue
                fit = _best_fit(free[day], remaining, room, profile, due, settings)
                if fit is not None and (best is None or (fit[1], room) > best[0]):
                    best = ((fit[1], room), day, *fit)
            if best is None:
                break
            _, day, i, length = best
            start, end = free[day][i]
            block_end = start + timedelta(minutes=length)
            blocks.append(WorkBlock(task.id, task.title, start, block_end))
            remaining -= length
            used[day] += length
            if block_end + gap < end:
                free[day][i] = (block_end + gap, end)
            else:
                free[day].pop(i)
        if remaining > 0:
            if task.due_at >= horizon_end:
                later.append(Shortfall(task, remaining, "échéance après la période planifiée"))
            else:
                at_risk.append(Shortfall(task, remaining, "pas assez de temps libre avant"))

    return Plan(
        start=now,
        zone=zone,
        energy_by_day=energy,
        events=tuple(events),
        blocks=tuple(sorted(blocks, key=lambda b: b.start)),
        at_risk=tuple(at_risk),
        later=tuple(later),
        conflicts=tuple(find_conflicts(events)),
    )
