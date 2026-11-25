"""A read-only copy of the demo as static files, for GitHub Pages (decision D71).

Each page is rendered by the real app (the demo mailbox, the recorded answers, the
frozen demo clock), then its links are made relative, so the copy works under any
address, such as https://<user>.github.io/<repository>/. Nothing runs on a server:
the controls that change the plan are shown disabled, with a banner that says so.
"""

import json
import re
import shutil
from pathlib import Path

from inbox_planner.web.app import create_app
from inbox_planner.web.state import AppData
from inbox_planner.web.store import LocalStore

HERE = Path(__file__).parent
PAGES = {
    "/": "index.html",
    "/jours": "jours.html",
    "/semaine": "semaine.html",
    "/echeances": "echeances.html",
    "/administratif": "administratif.html",
}
FILES = {"/export.ics": "export.ics", "/api/calendrier": "api/calendrier.json"}
# An app path in an attribute: href="/jours", src="/static/week.js", data-events="/api/...".
LINK = re.compile(r'(\s(?:href|src|data-events)=")(/[^"/][^"]*|/)"')


def target(path: str) -> str | None:
    """The static file for an app path ("/jours" -> "jours.html"), or None."""
    if path in PAGES:
        return PAGES[path]
    if path in FILES:
        return FILES[path]
    if path.startswith("/static/"):
        return path.removeprefix("/")
    message_id = path.removeprefix("/mails/")
    if path.startswith("/mails/") and message_id and "/" not in message_id:
        return f"mails/{message_id}.html"
    return None


def relative(path: str, depth: int) -> str:
    """The link to use in a file that is `depth` folders down; unknown paths stay as they are."""
    file = target(path)
    return "../" * depth + file if file else path


def rewrite(html: str, depth: int) -> str:
    return LINK.sub(lambda m: f'{m.group(1)}{relative(m.group(2), depth)}"', html)


def export_site(output: Path, data: AppData | None = None) -> list[Path]:
    """Write the static copy into `output` (emptied first) and return the files written."""
    from fastapi.testclient import TestClient  # a development dependency, like this export

    data = data or AppData.demo_mailbox()
    client = TestClient(create_app(data, LocalStore("sqlite://"), static_site=True))
    if output.exists():
        shutil.rmtree(output)
    written: list[Path] = []

    def write(name: str, content: str | bytes) -> None:
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        written.append(path)

    paths = [*PAGES, *(f"/mails/{message_id}" for message_id in sorted(data.processed))]
    for path in paths:
        response = client.get(path)
        response.raise_for_status()
        name = target(path)
        assert name is not None
        write(name, rewrite(response.text, name.count("/")))

    # The calendar feed: the links in the detail of an item point to the static mail pages,
    # relative to the week page, which sits at the root of the site.
    feed = client.get("/api/calendrier").json()
    for event in feed:
        info = event["extendedProps"]
        if info.get("mail"):
            info["mail"] = relative(info["mail"], 0)
        for part in info.get("parts", []):
            if part.get("mail"):
                part["mail"] = relative(part["mail"], 0)
    write(FILES["/api/calendrier"], json.dumps(feed, ensure_ascii=False))
    write(FILES["/export.ics"], client.get("/export.ics").content)

    for asset in sorted((HERE / "static").iterdir()):
        write(f"static/{asset.name}", asset.read_bytes())
    return written
