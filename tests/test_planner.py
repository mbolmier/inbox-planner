from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hypothesis import given, settings
from hypothesis import strategies as st

from inbox_planner.planning.calendar import Event, build_events, occurrences
from inbox_planner.planning.energy import PROFILES, Energy, suggested_energy
from inbox_planner.planning.planner import (
    PlannerSettings,
    Task,
    find_conflicts,
    plan_week,
    tasks_from_items,
)
from inbox_planner.schemas import ExtractedItem, Priority

OREGON = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 26, 8, 0, tzinfo=OREGON)  # the demo clock, a Monday
MONDAY = NOW.date()
SETTINGS = PlannerSettings()
GAP = timedelta(minutes=SETTINGS.gap_minutes)


def at(day_offset: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(MONDAY + timedelta(days=day_offset), time(hour, minute), tzinfo=OREGON)


def task(id: str, due: datetime, minutes: int, priority: Priority = Priority.MEDIUM) -> Task:
    return Task(id=id, title=id, due_at=due, minutes=minutes, priority=priority)


def event(start: datetime, minutes: int, title: str = "class") -> Event:
    return Event(title=title, start=start, end=start + timedelta(minutes=minutes))


def all_days(energy: Energy) -> dict[date, Energy]:
    return {MONDAY + timedelta(days=n): energy for n in range(7)}


def session_lengths(plan) -> list[int]:
    """Minutes of each work session: blocks that follow each other without a break."""
    lengths: list[int] = []
    previous = None
    for block in sorted(plan.blocks, key=lambda b: b.start):
        if previous is not None and previous.end == block.start:
            lengths[-1] += block.minutes
        else:
            lengths.append(block.minutes)
        previous = block
    return lengths


def minutes_per_task(plan) -> dict[str, int]:
    totals: dict[str, int] = {}
    for block in plan.blocks:
        totals[block.task_id] = totals.get(block.task_id, 0) + block.minutes
    return totals


# --- weekly classes and clock changes -------------------------------------------


def test_weekly_class_keeps_its_local_time_after_the_clock_change():
    # As in the labels: a fixed -07:00 offset, written in September.
    lecture = ExtractedItem(
        kind="appointment",
        title="ST 411 lecture",
        starts_at=datetime.fromisoformat("2026-09-23T10:00:00-07:00"),
        duration_minutes=50,
        weekly_on=("MO", "WE", "FR"),
        repeat_until=date(2026, 12, 4),
    )

    starts = occurrences(lecture, at(2, 0), at(9, 23), OREGON)

    assert [s.isoformat() for s in starts] == [
        "2026-10-28T10:00:00-07:00",  # Wednesday, summer time
        "2026-10-30T10:00:00-07:00",  # Friday
        "2026-11-02T10:00:00-08:00",  # Monday after the change: still 10:00 local
        "2026-11-04T10:00:00-08:00",
    ]


def test_weekly_class_stops_after_its_last_day_and_never_starts_before_the_first():
    lab = ExtractedItem(
        kind="appointment",
        title="lab",
        starts_at=datetime(2026, 10, 29, 14, 0, tzinfo=OREGON),
        weekly_on=("TH",),
        repeat_until=date(2026, 11, 5),
    )

    starts = occurrences(lab, at(-30, 0), at(60, 0), OREGON)

    assert [s.date() for s in starts] == [date(2026, 10, 29), date(2026, 11, 5)]


def test_events_are_built_only_from_appointments():
    items = {
        "m1": (
            ExtractedItem(kind="appointment", title="meeting", starts_at=at(1, 9)),
            ExtractedItem(kind="deadline", title="homework", due_at=at(2, 23, 59)),
        )
    }

    [built] = build_events(items, NOW, at(7, 0), OREGON)

    assert (built.title, built.message_id, built.end - built.start) == (
        "meeting",
        "m1",
        timedelta(minutes=60),
    )


# --- planning rules ----------------------------------------------------------------


def test_earliest_deadline_is_worked_on_first():
    tasks = [task("late", at(4, 18), 60), task("soon", at(1, 18), 60)]

    plan = plan_week(tasks, [], NOW, OREGON)

    first = min(plan.blocks, key=lambda b: b.start)
    assert first.task_id == "soon"


def test_work_is_spread_over_the_days_before_the_deadline():
    tasks = [task(f"t{n}", at(3, 18), 60) for n in range(3)]

    plan = plan_week(tasks, [], NOW, OREGON)

    days = {b.task_id: b.start.astimezone(OREGON).date() for b in plan.blocks}
    assert days == {"t0": MONDAY, "t1": at(1, 0).date(), "t2": at(2, 0).date()}


def test_a_day_in_good_shape_takes_more_of_the_work():
    tuesday = at(1, 0).date()
    energy = all_days(Energy.NORMAL) | {tuesday: Energy.ENERGIZED}

    plan = plan_week([task(f"t{n}", at(1, 20), 60) for n in range(5)], [], NOW, OREGON, energy)

    worked = {MONDAY: 0, tuesday: 0}
    for block in plan.blocks:
        worked[block.start.astimezone(OREGON).date()] += block.minutes
    assert worked == {MONDAY: 120, tuesday: 180}


def test_same_deadline_goes_by_priority():
    tasks = [task("low", at(1, 18), 30, Priority.LOW), task("high", at(1, 18), 30, Priority.HIGH)]

    plan = plan_week(tasks, [], NOW, OREGON)

    assert plan.blocks[0].task_id == "high"


def test_an_off_day_gets_no_work():
    energy = all_days(Energy.NORMAL) | {MONDAY: Energy.OFF}

    plan = plan_week([task("t", at(3, 18), 120)], [], NOW, OREGON, energy)

    assert all(b.start.astimezone(OREGON).date() != MONDAY for b in plan.blocks)


def test_a_tired_day_has_short_sessions_and_little_work():
    plan = plan_week([task("big", at(6, 20), 600)], [], NOW, OREGON, all_days(Energy.TIRED))

    monday = [b for b in plan.blocks if b.start.astimezone(OREGON).date() == MONDAY]
    assert sum(b.minutes for b in monday) <= PROFILES[Energy.TIRED].capacity_minutes
    assert all(s <= PROFILES[Energy.TIRED].max_session_minutes for s in session_lengths(plan))


def test_the_work_of_a_day_forms_one_session_from_nine_in_the_morning():
    tasks = [task("a", at(0, 20), 60), task("b", at(0, 20), 60)]

    plan = plan_week(tasks, [event(at(0, 13), 60)], NOW, OREGON)

    assert [
        (b.start.astimezone(OREGON).time(), b.end.astimezone(OREGON).time()) for b in plan.blocks
    ] == [
        (time(9, 0), time(10, 0)),
        (time(10, 0), time(11, 0)),
    ]


def test_a_class_in_the_way_splits_the_work_into_two_sessions():
    # 10:00-10:50 class: 9:00-9:50 is too short for an hour, the session starts at 11:00.
    plan = plan_week([task("a", at(0, 20), 60)], [event(at(0, 10), 50)], NOW, OREGON)

    [block] = plan.blocks
    assert block.start.astimezone(OREGON).time() == time(11, 0)


def test_work_never_lands_on_an_appointment_or_its_margin():
    classes = [event(at(0, 9), 120), event(at(0, 13), 60)]

    plan = plan_week([task("t", at(0, 20), 240)], classes, NOW, OREGON)

    for block in plan.blocks:
        for e in classes:
            assert block.end + GAP <= e.start or block.start >= e.end + GAP


def test_no_crumbs_when_a_task_is_split():
    # 130 minutes on a day "En forme" (2-hour sessions) gives 105 + 25, not 120 + 10.
    plan = plan_week([task("t", at(0, 20), 130)], [], NOW, OREGON, all_days(Energy.ENERGIZED))

    assert [b.minutes for b in plan.blocks] == [105, 25]


def test_not_enough_time_before_the_deadline_is_flagged():
    plan = plan_week([task("t", at(0, 10), 300)], [], NOW, OREGON)

    [shortfall] = plan.at_risk
    assert shortfall.missing_minutes == 300 - sum(b.minutes for b in plan.blocks)
    assert all(b.end <= at(0, 10) for b in plan.blocks)


def test_a_past_deadline_is_flagged_and_not_scheduled():
    plan = plan_week([task("t", at(0, 7), 60)], [], NOW, OREGON)

    assert not plan.blocks
    assert plan.at_risk[0].reason == "échéance déjà passée"


def test_work_left_for_a_deadline_after_the_horizon_is_postponed_not_at_risk():
    plan = plan_week([task("t", at(20, 18), 2000)], [], NOW, OREGON)

    assert not plan.at_risk
    assert plan.later[0].missing_minutes == 2000 - sum(b.minutes for b in plan.blocks)


def test_overlapping_appointments_are_reported():
    check_in, lab, later_class = event(at(3, 14), 20), event(at(3, 14), 110), event(at(3, 16), 80)

    assert find_conflicts([check_in, lab, later_class]) == [(check_in, lab)]


def test_same_input_same_plan():
    tasks = [task("a", at(2, 18), 90), task("b", at(1, 12), 45), task("c", at(5, 9), 200)]
    classes = [event(at(1, 10), 80), event(at(2, 14), 60)]

    assert plan_week(tasks, classes, NOW, OREGON) == plan_week(tasks, classes, NOW, OREGON)


def test_deadlines_become_tasks_with_a_default_estimate():
    items = {
        "m9": (
            ExtractedItem(kind="deadline", title="proposal", due_at=at(4, 17)),
            ExtractedItem(kind="deadline", title="test", due_at=at(5, 20), duration_minutes=180),
        )
    }

    tasks = tasks_from_items(items)

    assert [(t.id, t.minutes) for t in tasks] == [("m9-0", 60), ("m9-1", 180)]


# --- properties: hundreds of random weeks, the rules always hold ----------------------

five_minute_steps = st.integers(min_value=0, max_value=7 * 24 * 12).map(lambda n: n * 5)
random_events = st.lists(
    st.builds(
        lambda offset, length: event(NOW + timedelta(minutes=offset), length),
        five_minute_steps,
        st.integers(min_value=10, max_value=240),
    ),
    max_size=12,
)
random_tasks = st.lists(
    st.tuples(
        st.integers(min_value=-180, max_value=10 * 24 * 60),
        st.integers(min_value=5, max_value=400),
        st.sampled_from(list(Priority)),
    ),
    max_size=10,
).map(
    lambda rows: [
        task(f"t{n}", NOW + timedelta(minutes=due), minutes, priority)
        for n, (due, minutes, priority) in enumerate(rows)
    ]
)
random_energy = st.lists(st.sampled_from(list(Energy)), min_size=7, max_size=7).map(
    lambda values: {MONDAY + timedelta(days=n): e for n, e in enumerate(values)}
)


@settings(max_examples=300, deadline=None)
@given(events=random_events, tasks=random_tasks, energy=random_energy)
def test_the_planning_rules_always_hold(events, tasks, energy):
    plan = plan_week(tasks, events, NOW, OREGON, energy)
    by_id = {t.id: t for t in tasks}
    blocks = sorted(plan.blocks, key=lambda b: b.start)

    # 1. Blocks never overlap: they follow each other (same session) or keep a break.
    for first, second in zip(blocks, blocks[1:], strict=False):
        assert first.end == second.start or first.end + GAP <= second.start
    for block in blocks:
        local_start, local_end = block.start.astimezone(OREGON), block.end.astimezone(OREGON)
        profile = PROFILES[energy[local_start.date()]]
        # 2. Never on an appointment or its margin.
        assert all(block.end + GAP <= e.start or block.start >= e.end + GAP for e in events)
        # 3. Never after its deadline, never in the past.
        assert block.start >= NOW and block.end <= by_id[block.task_id].due_at
        # 4. Inside the working day.
        assert local_start.time() >= SETTINGS.day_start
        assert local_end.date() == local_start.date() and local_end.time() <= SETTINGS.day_end
        # 5. No crumbs.
        assert block.minutes >= min(SETTINGS.min_block_minutes, by_id[block.task_id].minutes)
        assert profile.capacity_minutes > 0
    # 5b. A work session is never longer than the energy of its day allows.
    previous, length = None, 0
    for block in blocks:
        length = (
            length + block.minutes if previous and previous.end == block.start else block.minutes
        )
        day = block.start.astimezone(OREGON).date()
        assert length <= PROFILES[energy[day]].max_session_minutes
        previous = block
    # 6. The work of a day never exceeds its capacity.
    for day, day_energy in energy.items():
        worked = sum(b.minutes for b in blocks if b.start.astimezone(OREGON).date() == day)
        assert worked <= PROFILES[day_energy].capacity_minutes
    # 7. Nothing is lost: planned + missing = estimated, for every task.
    planned = minutes_per_task(plan)
    missing = {s.task.id: s.missing_minutes for s in (*plan.at_risk, *plan.later)}
    for t in tasks:
        assert planned.get(t.id, 0) + missing.get(t.id, 0) == t.minutes
    # 8. Computed in UTC, so the plan does not depend on the zone of the input.
    assert plan == plan_week(tasks, events, NOW.astimezone(UTC), OREGON, energy)


def test_suggested_energy_follows_the_week_and_the_classes():
    busy_wednesday = [event(at(2, 9), 120), event(at(2, 13), 130)]  # 4 h 10

    assert suggested_energy(MONDAY, [], OREGON) is Energy.ENERGIZED
    assert suggested_energy(at(1, 0).date(), [], OREGON) is Energy.NORMAL
    assert suggested_energy(at(2, 0).date(), busy_wednesday, OREGON) is Energy.TIRED
    assert suggested_energy(at(4, 0).date(), [], OREGON) is Energy.TIRED  # Friday
