"""IMAP connector, read-only by protocol.

The folder is opened with EXAMINE (imaplib's `readonly=True`), which the server
guarantees read-only: no flag change, no deletion. Messages are fetched with
BODY.PEEK[], so they are not even marked as read. Only the standard library
is used.

Use an app password (Gmail, iCloud, Outlook.com...). University Microsoft 365
accounts refuse passwords over IMAP and require OAuth 2.0, which this connector
does not do.
"""

import contextlib
import imaplib
import ssl
from collections.abc import Callable
from datetime import datetime
from typing import Any

from inbox_planner.mail.models import Message
from inbox_planner.mail.parsing import parse_rfc822

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def imap_date(moment: datetime) -> str:
    """IMAP dates use English month names, whatever the computer's language."""
    return f"{moment.day:02d}-{MONTHS[moment.month - 1]}-{moment.year}"


def _ssl_client(host: str, port: int) -> Any:
    return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())


class ImapConnector:
    name = "imap"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        mailbox: str = "imap",
        folder: str = "INBOX",
        port: int = 993,
        max_messages: int = 100,
        client_factory: Callable[[str, int], Any] = _ssl_client,
    ) -> None:
        self.host, self.port, self.folder = host, port, folder
        self.mailbox, self.max_messages = mailbox, max_messages
        self._username, self._password = username, password
        self._client_factory = client_factory

    def fetch_messages(self, since: datetime | None = None) -> list[Message]:
        client = self._client_factory(self.host, self.port)
        self.skipped = 0
        try:
            client.login(self._username, self._password)
            status, _ = client.select(self.folder, readonly=True)  # EXAMINE: read-only
            if status != "OK":
                raise ConnectionError(f"cannot open folder {self.folder!r}")
            criteria = ("SINCE", imap_date(since)) if since else ("ALL",)
            status, data = client.uid("SEARCH", None, *criteria)
            uids = data[0].split()[-self.max_messages :] if status == "OK" and data[0] else []
            messages = []
            for uid in uids:
                status, parts = client.uid("FETCH", uid, "(BODY.PEEK[])")  # PEEK: stays unread
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if status == "OK" and raw:
                    message_id = f"{self.folder}:{uid.decode()}"
                    try:
                        messages.append(
                            parse_rfc822(raw, mailbox=self.mailbox, message_id=message_id)
                        )
                    except ValueError:  # malformed e-mail: skipped, never fatal
                        self.skipped += 1
        finally:
            with contextlib.suppress(imaplib.IMAP4.error, OSError):
                client.logout()
        if since is not None:
            messages = [m for m in messages if m.sent_at >= since]
        return sorted(messages, key=lambda m: m.sent_at)
