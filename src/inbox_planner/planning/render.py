"""Plain-text view of a plan, in French, for the terminal."""

from datetime import date, datetime, timedelta

from inbox_planner.planning.energy import PROFILES
from inbox_planner.planning.planner import Plan

DAYS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
TITLE_WIDTH = 60


def day_label(day: date) -> str:
    return f"{DAYS_FR[day.weekday()].capitalize()} {day:%d/%m}"


def hours(minutes: int) -> str:
    whole, rest = divmod(minutes, 60)
    return f"{whole} h {rest:02d}" if rest else f"{whole} h"


def short_title(title: str, width: int = TITLE_WIDTH) -> str:
    return title if len(title) <= width else title[: width - 1].rstrip() + "…"


def render_plan(plan: Plan) -> str:
    def local(moment: datetime) -> datetime:
        return moment.astimezone(plan.zone)

    def span(start: datetime, end: datetime) -> str:
        return f"{local(start):%H:%M}-{local(end):%H:%M}"

    lines = [f"Semaine du {day_label(min(plan.energy_by_day))} ({plan.zone.key})", ""]
    for day, energy in plan.energy_by_day.items():
        profile = PROFILES[energy]
        rows = []
        for event in plan.events:
            if local(event.start).date() == day:
                where = f" ({event.location})" if event.location else ""
                video = " [visio]" if event.video_url else ""
                rows.append(
                    (
                        local(event.start),
                        f"{span(event.start, event.end)}  RDV      "
                        f"{short_title(event.title)}{where}{video}",
                    )
                )
        worked = 0
        for block in plan.blocks:
            if local(block.start).date() == day:
                worked += block.minutes
                rows.append(
                    (
                        local(block.start),
                        f"{span(block.start, block.end)}  TRAVAIL  {short_title(block.title)}",
                    )
                )
        lines.append(
            f"{day_label(day)} · énergie {profile.label_fr} · "
            f"travail prévu {hours(worked)} / {hours(profile.capacity_minutes)}"
        )
        lines += [f"  {text}" for _, text in sorted(rows)] or ["  (rien)"]
        lines.append("")

    if plan.conflicts:
        lines.append("CONFLITS (deux rendez-vous en même temps) :")
        for first, second in plan.conflicts:
            lines.append(
                f"  {day_label(local(first.start).date())} : {short_title(first.title, 40)} "
                f"({span(first.start, first.end)}) et {short_title(second.title, 40)} "
                f"({span(second.start, second.end)})"
            )
        lines.append("")
    if plan.at_risk:
        lines.append("À RISQUE (pas assez de temps avant l'échéance) :")
        for s in plan.at_risk:
            due = local(s.task.due_at)
            lines.append(
                f"  {short_title(s.task.title)} : il manque {hours(s.missing_minutes)}, "
                f"échéance {day_label(due.date())} {due:%H:%M} ({s.reason})"
            )
        lines.append("")
    if plan.later:
        end = min(plan.energy_by_day) + timedelta(days=len(plan.energy_by_day))
        lines.append(f"À planifier après le {day_label(end)} :")
        lines += [f"  {short_title(s.task.title)} ({hours(s.missing_minutes)})" for s in plan.later]
    return "\n".join(lines).rstrip() + "\n"
