"""Demo connector: a fictional mailbox shipped with the package.

The mailbox is a readable TOML file. Each entry is turned into a real RFC 5322
e-mail, then parsed by the same code as the real connectors, so the demo goes
through the real parsing path. No account, no network.
"""

import tomllib
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from inbox_planner.mail.models import Message
from inbox_planner.mail.parsing import parse_rfc822

DEFAULT_MAILBOX: Traversable = files("inbox_planner") / "demo_data" / "mailbox.toml"

# The demo clock is frozen: the dates in the fictional mailbox are the ground
# truth of the evaluation, so "now" cannot move. During this week Paris has left
# summer time (25 Oct) but Oregon has not (1 Nov): the gap is 8 hours, not 9.
DEMO_NOW = datetime(2026, 10, 26, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles"))

# Default time zone of each demo mailbox: what a real installation would configure.
DEMO_TIMEZONES = {
    "lyon2": "Europe/Paris",
    "osu": "America/Los_Angeles",
    "personal": "America/Los_Angeles",  # the student lives in Oregon this term
}


class DemoConnector:
    """Read-only access to the fictional mailbox."""

    name = "demo"

    def __init__(self, path: Path | Traversable = DEFAULT_MAILBOX) -> None:
        self._path = path

    def fetch_messages(self, since: datetime | None = None) -> list[Message]:
        entries = tomllib.loads(self._path.read_text(encoding="utf-8"))["message"]
        messages = [
            parse_rfc822(_to_rfc822(entry), mailbox=entry["mailbox"], message_id=entry["id"])
            for entry in entries
        ]
        if since is not None:
            messages = [m for m in messages if m.sent_at >= since]
        return sorted(messages, key=lambda m: m.sent_at)


def _to_rfc822(entry: dict[str, Any]) -> bytes:
    """Build the raw bytes a real mail server would return for this entry."""
    sent_at = entry["date"]
    if not isinstance(sent_at, datetime) or sent_at.tzinfo is None:
        raise ValueError(f"demo message {entry['id']}: date must include a UTC offset")

    msg = EmailMessage()
    msg["Message-ID"] = f"<{entry['id']}@demo.inbox-planner.example>"
    msg["From"] = entry["from"]
    msg["To"] = entry["to"]
    msg["Subject"] = entry["subject"]
    msg["Date"] = format_datetime(sent_at)

    text, html = entry.get("text"), entry.get("html")
    if text:
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
    elif html:
        msg.set_content(html, subtype="html")
    else:
        raise ValueError(f"demo message {entry['id']}: needs a text or html body")
    return msg.as_bytes()
