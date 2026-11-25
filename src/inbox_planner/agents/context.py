"""How an e-mail is shown to the model.

The model gets what a real installation would know: the mailbox, its default
time zone, and the sending date with its weekday (needed for "this Monday").
"""

from collections.abc import Mapping
from zoneinfo import ZoneInfo

from inbox_planner.mail.models import Message


def render_message(message: Message, timezones: Mapping[str, str]) -> str:
    zone_name = timezones.get(message.mailbox, "UTC")
    sent = message.sent_at.astimezone(ZoneInfo(zone_name))
    offset = sent.strftime("%z")
    return (
        f"Mailbox: {message.mailbox} (default time zone: {zone_name})\n"
        f"From: {message.sender}\n"
        f"To: {', '.join(message.recipients)}\n"
        f"Sent: {sent:%A %Y-%m-%d %H:%M} ({zone_name}, UTC{offset[:3]}:{offset[3:]})\n"
        f"Subject: {message.subject}\n"
        f"\n{message.body_text}\n"
    )
