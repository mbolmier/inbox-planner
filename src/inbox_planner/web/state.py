"""What the pages show, computed from the demo mailbox and the recorded answers."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from inbox_planner.connectors.demo import DEMO_NOW, DEMO_TIMEZONES, DemoConnector
from inbox_planner.llm.base import LLMClient
from inbox_planner.llm.cache import CachedClient
from inbox_planner.locations import Place, resolve_place
from inbox_planner.pipeline import ProcessedMessage, items_by_message, process_mailbox
from inbox_planner.planning.calendar import Event, build_events
from inbox_planner.planning.energy import Energy
from inbox_planner.planning.planner import Plan, PlannerSettings, Task, plan_week, tasks_from_items
from inbox_planner.schemas import Category, ExtractedItem, Priority

# Area added to a map search when the place does not name its town (demo mailboxes).
DEMO_AREAS = {"osu": "Corvallis, OR", "lyon2": "Lyon"}
HOME_ZONE = ZoneInfo("Europe/Paris")  # shown next to the local time


@dataclass(frozen=True)
class AgendaEntry:
    kind: str  # "event", "work" or "deadline"
    category: str  # css class: cours, rdv, visio, travail, echeance, demarche
    title: str
    start: datetime  # local time
    end: datetime
    place: Place | None = None
    message_id: str | None = None


@dataclass(frozen=True)
class DeadlineRow:
    task: Task
    due: datetime  # local time
    category: str
    planned_minutes: int
    missing_minutes: int
    status: str  # planifiée, à risque, dépassée, à suivre


@dataclass(frozen=True)
class DemoData:
    now: datetime
    zone: ZoneInfo
    processed: dict[str, ProcessedMessage]
    items: dict[str, tuple[ExtractedItem, ...]]
    settings: PlannerSettings

    @classmethod
    def load(cls, llm: LLMClient | None = None) -> "DemoData":
        processed = process_mailbox(
            DemoConnector(), llm or CachedClient(), DEMO_TIMEZONES, now=DEMO_NOW
        )
        return cls(
            now=DEMO_NOW,
            zone=ZoneInfo(DEMO_TIMEZONES["osu"]),
            processed={p.message.id: p for p in processed},
            items=items_by_message(processed),
            settings=PlannerSettings(),
        )

    @property
    def days(self) -> list[date]:
        first = self.now.astimezone(self.zone).date()
        return [first + timedelta(days=n) for n in range(self.settings.horizon_days)]

    @property
    def tasks(self) -> list[Task]:
        return tasks_from_items(self.items, self.settings)

    def events(self) -> list[Event]:
        end = self.now + timedelta(days=self.settings.horizon_days)
        return build_events(self.items, self.now, end, self.zone)

    def plan(self, energy_by_day: Mapping[date, Energy]) -> Plan:
        return plan_week(
            self.tasks, self.events(), self.now, self.zone, energy_by_day, self.settings
        )

    def area_of(self, message_id: str | None) -> str | None:
        processed = self.processed.get(message_id or "")
        return DEMO_AREAS.get(processed.message.mailbox) if processed else None

    def deadline_category(self, message_id: str | None) -> str:
        processed = self.processed.get(message_id or "")
        triage = processed.triage if processed else None
        return "demarche" if triage and triage.category is Category.PROCEDURE else "echeance"


def _event_category(event: Event) -> str:
    if event.weekly:
        return "cours"
    return "visio" if event.video_url else "rdv"


def agenda(data: DemoData, plan: Plan, day: date) -> list[AgendaEntry]:
    """Appointments, planned work and deadlines of one day, in time order."""
    local = data.zone
    entries = []
    for event in plan.events:
        if event.start.astimezone(local).date() == day:
            place = resolve_place(
                event.location,
                event.video_url,
                event.meeting_id,
                event.passcode,
                data.area_of(event.message_id),
            )
            entries.append(
                AgendaEntry(
                    "event",
                    _event_category(event),
                    event.title,
                    event.start.astimezone(local),
                    event.end.astimezone(local),
                    place,
                    event.message_id,
                )
            )
    tasks = {t.id: t for t in data.tasks}
    for block in plan.blocks:
        if block.start.astimezone(local).date() == day:
            entries.append(
                AgendaEntry(
                    "work",
                    "travail",
                    block.title,
                    block.start.astimezone(local),
                    block.end.astimezone(local),
                    message_id=tasks[block.task_id].message_id,
                )
            )
    for task in data.tasks:
        due = task.due_at.astimezone(local)
        if due.date() == day:
            entries.append(
                AgendaEntry(
                    "deadline",
                    data.deadline_category(task.message_id),
                    task.title,
                    due,
                    due,
                    message_id=task.message_id,
                )
            )
    return sorted(entries, key=lambda e: (e.start, e.kind != "deadline", e.title))


def deadline_rows(data: DemoData, plan: Plan) -> list[DeadlineRow]:
    """Every deadline, most urgent first, with how much of it is planned."""
    planned: dict[str, int] = {}
    for block in plan.blocks:
        planned[block.task_id] = planned.get(block.task_id, 0) + block.minutes
    shortfalls = {s.task.id: s for s in (*plan.at_risk, *plan.later)}
    rows = []
    for task in data.tasks:
        shortfall = shortfalls.get(task.id)
        if shortfall is None:
            status = "planifiée"
        elif shortfall.reason == "échéance déjà passée":
            status = "dépassée"
        elif shortfall in plan.later:
            status = "à suivre"
        else:
            status = "à risque"
        rows.append(
            DeadlineRow(
                task=task,
                due=task.due_at.astimezone(data.zone),
                category=data.deadline_category(task.message_id),
                planned_minutes=planned.get(task.id, 0),
                missing_minutes=shortfall.missing_minutes if shortfall else 0,
                status=status,
            )
        )
    rank = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    return sorted(rows, key=lambda r: (r.task.due_at, rank[r.task.priority], r.task.id))
