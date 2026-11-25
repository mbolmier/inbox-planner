"""Deterministic planner: earliest deadline first, in work sessions spread over the days.

Tasks are taken by due date (then priority). Their work is spread out: each
block goes to the day before the deadline that can take the longest block, then
to the day with the most work capacity left, then to the earliest day. Inside a
day, the work forms sessions: a block extends the day's session when it can,
otherwise it opens a new one at the earliest free time. So a day usually has one
work session, two when a class is in the way. Sessions start at 9:00 at the
earliest, are never longer than the day's energy allows, never over an
appointment or its margin, never beyond the day's work capacity. Times are
computed in UTC and only shown in local time.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from inbox_planner.planning.calendar import Event
from inbox_planner.planning.energy import PROFILES, Energy
from inbox_planner.schemas import ExtractedItem, ItemKind, Priority

PRIORITY_RANK = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
Interval = tuple[datetime, datetime]  # [start, end) in UTC


@dataclass(frozen=True)
class PlannerSettings:
    day_start: time = time(9, 0)  # no personal work before 9:00
    day_end: time = time(20, 0)
    gap_minutes: int = 10  # around appointments and between two work sessions
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
    sessions: dict[date, list[Interval]] = {day: [] for day in days}
    used = dict.fromkeys(days, 0)
    blocks: list[WorkBlock] = []
    at_risk: list[Shortfall] = []
    later: list[Shortfall] = []

    def options(day: date, remaining: int, due: datetime) -> list[tuple[tuple, int, datetime]]:
        """Ways to place the next block on a day: (preference, kind, start), the best
        preference first. Kind 0 extends a session at its end, kind 1 opens a session.

        Preference: the longest block (no task cut for nothing); then extending a
        session rather than opening one; then, to open one, the first free period
        long enough for a whole session (not a crumb of time before a class),
        failing that the longest free period."""
        profile = PROFILES[energy[day]]
        room = profile.capacity_minutes - used[day]
        if room <= 0:
            return []
        found = []
        for s_start, s_end in sessions[day]:
            limit_end = next(b for a, b in free[day] if a <= s_start < b)
            for other_start, _ in sessions[day]:
                if other_start > s_end:
                    limit_end = min(limit_end, other_start - gap)
            limit = min(
                profile.max_session_minutes - _minutes(s_end - s_start),
                room,
                _minutes(min(limit_end, due) - s_end),
            )
            length = _block_length(remaining, limit, settings.min_block_minutes)
            if length > 0:
                found.append(((length, 1, 1, 0.0), 0, s_end))
        open_time = free[day]
        for s_start, s_end in sessions[day]:
            open_time = _subtract(open_time, (s_start - gap, s_end + gap))
        whole_session = min(profile.max_session_minutes, room)
        for a, b in open_time:
            usable = _minutes(min(b, due) - a)
            limit = min(profile.max_session_minutes, room, usable)
            length = _block_length(remaining, limit, settings.min_block_minutes)
            if length > 0:
                fits = usable >= whole_session
                found.append(((length, 0, int(fits), -a.timestamp() if fits else usable), 1, a))
        return sorted(found, key=lambda o: o[0], reverse=True)

    for task in sorted(tasks, key=lambda t: (t.due_at, PRIORITY_RANK[t.priority], t.id)):
        due = task.due_at.astimezone(UTC)
        if due <= now:
            at_risk.append(Shortfall(task, task.minutes, "échéance déjà passée"))
            continue
        remaining = task.minutes
        while remaining > 0:
            # The day: the one that can take the longest block (a task is not cut into
            # pieces for nothing), then the one with the most capacity left, then the
            # earliest. Inside the day: the longest block, extending a session rather
            # than opening one, then the earliest time.
            # A day where the block would open a second session comes after the days
            # where it extends one or opens the day's first.
            best: tuple[tuple[int, int, int], date, tuple[tuple, int, datetime]] | None = None
            for day in days:
                found = options(day, remaining, due)
                if not found:
                    continue
                choice = found[0]
                length, kind = choice[0][0], choice[1]
                extra_session = kind == 1 and bool(sessions[day])
                room = PROFILES[energy[day]].capacity_minutes - used[day]
                key = (length, int(not extra_session), room)
                if best is None or key > best[0]:
                    best = (key, day, choice)
            if best is None:
                break
            (length, _, _), day, (_, kind, start) = best
            block_end = start + timedelta(minutes=length)
            blocks.append(WorkBlock(task.id, task.title, start, block_end))
            remaining -= length
            used[day] += length
            if kind == 0:
                k = next(i for i, (_, s_end) in enumerate(sessions[day]) if s_end == start)
                sessions[day][k] = (sessions[day][k][0], block_end)
            else:
                sessions[day].append((start, block_end))
                sessions[day].sort()
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
