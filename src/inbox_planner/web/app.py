"""FastAPI application: today, the week, deadlines, the source e-mails, .ics export.

Security choices:
- mail bodies are always shown as escaped text, never as HTML: no script and
  no tracking pixel from an e-mail can run in the app;
- a strict Content-Security-Policy: scripts only from this app and the pinned
  CDN files (checked with SRI hashes in the templates);
- requests that change something must carry the HX-Request header, which a
  plain cross-site form cannot send: a simple CSRF protection;
- no Referer is sent when a Maps or meeting link is opened.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Protocol
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from inbox_planner.agents.drafting import INSTRUCTIONS, can_reply
from inbox_planner.export.ics import build_calendar
from inbox_planner.llm.base import CacheMiss, LLMError
from inbox_planner.locations import resolve_place
from inbox_planner.mail.compose import DraftReply
from inbox_planner.mail.models import Message
from inbox_planner.planning.energy import PROFILES, Energy, suggested_energy
from inbox_planner.planning.render import DAYS_FR, hours
from inbox_planner.schemas import Category
from inbox_planner.web.links import linkify
from inbox_planner.web.state import HOME_ZONE, AppData, agenda, deadline_rows
from inbox_planner.web.store import LocalStore

HERE = Path(__file__).parent
MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip
CATEGORY_FR = {
    Category.APPOINTMENT: "Rendez-vous",
    Category.DEADLINE: "Échéance",
    Category.PROCEDURE: "Démarche",
    Category.INFO: "Info",
    Category.NOISE: "Bruit",
}
STATUS_SLUG = {
    "planifiée": "ok",
    "à risque": "risk",
    "dépassée": "late",
    "à suivre": "later",
    "faite": "done",
}
KIND_FR = {
    "cours": "Cours",
    "rdv": "Rendez-vous",
    "visio": "Visio",
    "travail": "Travail",
    "echeance": "Échéance",
    "demarche": "Démarche",
}
CSP = (
    "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def day_label(day: date, with_month: bool = False) -> str:
    name = DAYS_FR[day.weekday()].capitalize()
    return f"{name} {day.day} {MONTHS_FR[day.month - 1]}" if with_month else f"{name} {day:%d/%m}"


def time_left(due: datetime, now: datetime) -> str:
    delta = due - now
    if delta.total_seconds() < 0:
        return "dépassée"
    days, seconds = delta.days, delta.seconds
    if days:
        return f"dans {days} j {seconds // 3600} h"
    return f"dans {seconds // 3600} h {seconds % 3600 // 60:02d}"


MAILBOX_FR = {"lyon2": "Université Lyon 2", "osu": "Oregon State University", "personal": "Perso"}


def duration(minutes: int) -> str:
    return f"{minutes} min" if minutes < 60 else hours(minutes)


def countdown(due: datetime, now: datetime, zone: ZoneInfo) -> tuple[str, str]:
    """Days left as in a paper planner, counted in calendar days of the local zone:
    (label, urgency). A deadline at 00:30 tomorrow is "demain", not "dans 16 h"."""
    if due < now:
        return "passée", "late"
    days = (due.astimezone(zone).date() - now.astimezone(zone).date()).days
    label = "auj." if days == 0 else "demain" if days == 1 else f"J-{days}"
    return label, "now" if days <= 1 else "soon" if days <= 3 else "later"


class DraftSink(Protocol):
    """Where an approved draft goes: local storage (demo) or the mailbox's drafts."""

    def save(self, original: Message, draft: DraftReply) -> str: ...


def create_app(
    data: AppData | None = None,
    store: LocalStore | None = None,
    draft_sink: DraftSink | None = None,
) -> FastAPI:
    data = data or AppData.demo_mailbox()
    store = store or LocalStore.from_env()
    sink: DraftSink = draft_sink or store
    app = FastAPI(title="inbox-planner", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters["hhmm"] = lambda moment: f"{moment:%H:%M}"
    templates.env.filters["day"] = day_label
    templates.env.filters["hours"] = hours
    templates.env.filters["duration"] = duration
    templates.env.filters["linkify"] = linkify
    templates.env.globals.update(
        profiles=PROFILES,
        energies=list(Energy),
        category_fr=CATEGORY_FR,
        status_slug=STATUS_SLUG,
        kind_fr=KIND_FR,
        home_zone=HOME_ZONE,
        time_left=lambda due: time_left(due, data.now),
        countdown=lambda due: countdown(due, data.now, data.zone),
        demo=data.demo,
        intents=list(INSTRUCTIONS),
        draft_target=getattr(sink, "label", "cet ordinateur"),
        item_place=lambda item, area: resolve_place(
            item.location, item.video_url, item.meeting_id, item.passcode, area
        ),
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def energy_by_day() -> dict[date, Energy]:
        """The energy chosen for each day, or the suggested one (D66) until then."""
        saved = store.energies()
        events = data.events()
        return {
            day: saved.get(day) or suggested_energy(day, events, data.zone) for day in data.days
        }

    def chosen_days() -> set[date]:
        return set(store.energies())

    def context(request: Request, page: str) -> dict:
        now = data.now.astimezone(data.zone)
        paris = data.now.astimezone(HOME_ZONE)
        gap = int((paris.utcoffset() - now.utcoffset()).total_seconds() // 3600)
        return {
            "request": request,
            "page": page,
            "now": now,
            "paris": paris,
            "gap_hours": gap,
            "zone": data.zone,
        }

    def today_context(request: Request) -> dict:
        energy = energy_by_day()
        done = store.done_tasks()
        plan = data.plan(energy, done)
        today = data.days[0]
        entries = agenda(data, plan, today, done)
        upcoming = [e for e in entries if e.end > data.now.astimezone(data.zone)]
        soon = [
            row
            for row in deadline_rows(data, plan, done)
            if data.now <= row.task.due_at < data.now + timedelta(days=len(data.days))
            and row.status != "faite"
        ]
        return context(request, "today") | {
            "day": today,
            "energy": energy[today],
            "energy_chosen": today in chosen_days(),
            "done": done,
            "entries": entries,
            "next_entry": next((e for e in upcoming if e.kind != "deadline"), None),
            "soon": soon,
            "worked": sum(
                b.minutes for b in plan.blocks if b.start.astimezone(data.zone).date() == today
            ),
        }

    @app.get("/", response_class=HTMLResponse)
    def today(request: Request):
        return templates.TemplateResponse(request, "today.html", today_context(request))

    def week_context(request: Request) -> dict:
        energy = energy_by_day()
        plan = data.plan(energy, store.done_tasks())
        worked = dict.fromkeys(data.days, 0)
        for block in plan.blocks:
            worked[block.start.astimezone(data.zone).date()] += block.minutes
        return context(request, "week") | {
            "days": data.days,
            "energy": energy,
            "worked": worked,
            "plan": plan,
        }

    def days_context(request: Request) -> dict:
        energy = energy_by_day()
        done = store.done_tasks()
        chosen = chosen_days()
        plan = data.plan(energy, done)
        worked = dict.fromkeys(data.days, 0)
        for block in plan.blocks:
            worked[block.start.astimezone(data.zone).date()] += block.minutes
        rows = [
            {
                "day": day,
                "energy": energy[day],
                "worked": worked[day],
                "capacity": PROFILES[energy[day]].capacity_minutes,
                "chosen": day in chosen,
                "entries": (entries := agenda(data, plan, day, done)),
                "classes": sum((e.end - e.start for e in entries if e.kind == "event"), timedelta())
                // timedelta(minutes=1),
            }
            for day in data.days
        ]
        return context(request, "days") | {
            "rows": rows,
            "today": data.days[0],
            "plan": plan,
            "done": done,
        }

    @app.get("/jours", response_class=HTMLResponse)
    def days(request: Request):
        return templates.TemplateResponse(request, "days.html", days_context(request))

    @app.get("/semaine", response_class=HTMLResponse)
    def week(request: Request):
        return templates.TemplateResponse(request, "week.html", week_context(request))

    @app.get("/echeances", response_class=HTMLResponse)
    def deadlines(request: Request):
        done = store.done_tasks()
        rows = deadline_rows(data, data.plan(energy_by_day(), done), done)
        return templates.TemplateResponse(
            request, "deadlines.html", context(request, "deadlines") | {"rows": rows, "done": done}
        )

    @app.get("/administratif", response_class=HTMLResponse)
    def administrative(request: Request):
        """The administrative procedures only, grouped by the organisation that asks."""
        done = store.done_tasks()
        rows = [
            r
            for r in deadline_rows(data, data.plan(energy_by_day(), done), done)
            if r.category == "demarche"
        ]
        groups: dict[str, list] = {}
        for row in rows:
            mailbox = data.mailbox_of(row.task.message_id) or ""
            groups.setdefault(MAILBOX_FR.get(mailbox, mailbox or "Autre"), []).append(row)
        return templates.TemplateResponse(
            request,
            "admin.html",
            context(request, "admin")
            | {
                "groups": groups,
                "done": done,
                "todo_count": sum(r.status != "faite" for r in rows),
                "done_count": sum(r.status == "faite" for r in rows),
            },
        )

    @app.get("/mails/{message_id}", response_class=HTMLResponse)
    def message(request: Request, message_id: str):
        processed = data.processed.get(message_id)
        if processed is None:
            raise HTTPException(status_code=404, detail="mail inconnu")
        items = data.items.get(message_id, ())
        return templates.TemplateResponse(
            request,
            "message.html",
            context(request, "mail")
            | {
                "processed": processed,
                "sent": processed.message.sent_at.astimezone(data.zone),
                "items": items,
                "area": data.areas.get(processed.message.mailbox),
                "can_reply": can_reply(processed.message),
            },
        )

    @app.get("/api/calendrier")
    def calendar_feed() -> JSONResponse:
        """Events for FullCalendar, as local wall-clock times: the browser shows them
        as they are, whatever its own time zone (a recruiter in Paris sees Oregon time)."""
        done = store.done_tasks()
        plan = data.plan(energy_by_day(), done)
        feed = []
        for day in data.days:
            for entry in agenda(data, plan, day, done):
                # A deadline is an instant: no end, so it never spills over midnight.
                is_deadline = entry.kind == "deadline"
                title = entry.title
                if is_deadline:
                    title = "Échéance : " + entry.parts[0].short
                feed.append(
                    {
                        "title": title,
                        "start": entry.start.replace(tzinfo=None).isoformat(),
                        "classNames": [f"cat-{entry.category}", f"kind-{entry.kind}"],
                        "extendedProps": detail(entry),
                    }
                    | ({} if is_deadline else {"end": entry.end.replace(tzinfo=None).isoformat()})
                )
        return JSONResponse(feed)

    def detail(entry) -> dict:
        """What the calendar shows when an item is clicked. Links are only the app's
        own pages, and https links already checked on the server."""
        time_text = f"{entry.start:%H:%M}" + (
            "" if entry.kind == "deadline" else f"–{entry.end:%H:%M}"
        )
        info: dict = {
            "kind": entry.kind,
            "title": entry.title,
            "day": day_label(entry.start),
            "time": time_text,
        }
        if entry.message_id:
            info["mail"] = f"/mails/{entry.message_id}"
        if entry.place:
            info["place"] = {
                "label": entry.place.label,
                "url": entry.place.url,
                "online": entry.place.online,
            }
        info["parts"] = [
            {
                "title": part.title,
                "short": part.short,
                "tag": "Démarche" if part.category == "demarche" else "Devoir",
                "time": f"{part.start:%H:%M}–{part.end:%H:%M}" if part.start else None,
                "minutes": duration(part.minutes),
                "due": f"{day_label(part.due)} {part.due:%H:%M}",
                "countdown": countdown(part.due, data.now, data.zone)[0],
                "urgency": countdown(part.due, data.now, data.zone)[1],
                "mail": f"/mails/{part.message_id}" if part.message_id else None,
                "site": part.site,
            }
            for part in entry.parts
        ]
        return info

    @app.post("/energie/{day}", response_class=HTMLResponse)
    def set_energy(
        request: Request,
        day: date,
        energy: Annotated[Energy, Form()],
        view: Annotated[str, Form()] = "today",
        hx_request: Annotated[str | None, Header()] = None,
    ):
        require_htmx(hx_request)
        if day not in data.days:
            raise HTTPException(status_code=404, detail="jour hors de la période planifiée")
        store.set_energy(day, energy)
        if view == "days":
            return templates.TemplateResponse(request, "_days.html", days_context(request))
        if view == "week":
            response = templates.TemplateResponse(
                request, "_week_energy.html", week_context(request)
            )
            response.headers["HX-Trigger"] = "planChanged"  # the calendar reloads its events
            return response
        return templates.TemplateResponse(request, "_day_plan.html", today_context(request))

    @app.post("/taches/{task_id}/fait")
    def mark_done(
        task_id: str,
        done: Annotated[bool, Form()] = False,
        hx_request: Annotated[str | None, Header()] = None,
    ) -> Response:
        """Tick or untick a task. Done tasks get no more work, so the page reloads."""
        require_htmx(hx_request)
        if task_id not in {t.id for t in data.tasks}:
            raise HTTPException(status_code=404, detail="tâche inconnue")
        store.set_done(task_id, done)
        return Response(status_code=204, headers={"HX-Refresh": "true"})

    def require_htmx(hx_request: str | None) -> None:
        if hx_request != "true":
            raise HTTPException(status_code=403, detail="requête refusée")

    def message_or_404(message_id: str) -> Message:
        processed = data.processed.get(message_id)
        if processed is None:
            raise HTTPException(status_code=404, detail="mail inconnu")
        return processed.message

    @app.post("/mails/{message_id}/reponse", response_class=HTMLResponse)
    def propose_reply(
        request: Request,
        message_id: str,
        intent: Annotated[str, Form()] = "confirmer",
        hx_request: Annotated[str | None, Header()] = None,
    ):
        """Step 1: the agent PROPOSES a reply. Nothing is written anywhere."""
        require_htmx(hx_request)
        message = message_or_404(message_id)
        if intent not in INSTRUCTIONS or not can_reply(message):
            raise HTTPException(status_code=400, detail="réponse impossible")
        error, draft = None, None
        try:
            draft = data.drafter().run(message, intent)
        except CacheMiss:
            error = "Cette réponse n'a pas été enregistrée pour la démo."
        except LLMError:
            error = "Le modèle n'a pas pu proposer de réponse. Réessaie plus tard."
        return templates.TemplateResponse(
            request,
            "_draft.html",
            context(request, "mail") | {"message": message, "draft": draft, "error": error},
        )

    @app.post("/mails/{message_id}/reponse/enregistrer", response_class=HTMLResponse)
    def save_reply(
        request: Request,
        message_id: str,
        to: Annotated[str, Form()],
        subject: Annotated[str, Form()],
        body: Annotated[str, Form()],
        hx_request: Annotated[str | None, Header()] = None,
    ):
        """Step 2: the user reviewed (and maybe edited) the text and clicked. Only now
        is a DRAFT written. Never sent."""
        require_htmx(hx_request)
        message = message_or_404(message_id)
        if not body.strip():
            raise HTTPException(status_code=400, detail="brouillon vide")
        draft = DraftReply(source_message_id=message.id, to=to, subject=subject, body=body)
        draft_id = sink.save(message, draft)
        return templates.TemplateResponse(
            request,
            "_draft_saved.html",
            context(request, "mail") | {"draft": draft, "draft_id": draft_id},
        )

    @app.get("/export.ics")
    def export(travail: bool = False) -> Response:
        plan = data.plan(energy_by_day(), store.done_tasks()) if travail else None
        body = build_calendar(
            data.items,
            {mid: p.message for mid, p in data.processed.items()},
            data.zone,
            data.areas,
            plan.blocks if plan else (),
        )
        return Response(
            body,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="inbox-planner.ics"'},
        )

    return app
