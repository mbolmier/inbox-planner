"""How an e-mail is shown to the model.

The model gets what a real installation would know: the reference time ("now",
which the app controls), the mailbox, its default time zone, and the sending
date with its weekday (needed for "this Monday"). Without an explicit "now",
the model falls back on the real date it may know, which is not the demo's.
"""

from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

from inbox_planner.mail.models import Message


def _stamp(moment: datetime, zone_name: str) -> str:
    local = moment.astimezone(ZoneInfo(zone_name))
    offset = local.strftime("%z")
    return f"{local:%A %Y-%m-%d %H:%M} ({zone_name}, UTC{offset[:3]}:{offset[3:]})"


def render_message(message: Message, timezones: Mapping[str, str], now: datetime | None) -> str:
    """`now=None` means "as of the e-mail's arrival": the reference time is its sending
    time. That is how a real installation works (each e-mail is analysed when it
    arrives), and it keeps the prompt, hence the cache key, stable over time."""
    zone_name = timezones.get(message.mailbox, "UTC")
    reference = now or message.sent_at
    return (
        f"Reference time (now): {_stamp(reference, zone_name)}\n"
        f"Mailbox: {message.mailbox} (default time zone: {zone_name})\n"
        f"From: {message.sender}\n"
        f"To: {', '.join(message.recipients)}\n"
        f"Sent: {_stamp(message.sent_at, zone_name)}\n"
        f"Subject: {message.subject}\n"
        f"\n{message.body_text}\n"
    )
