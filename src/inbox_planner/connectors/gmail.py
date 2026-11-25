"""Gmail connector (official API). Reading, plus draft creation on demand.

Messages are fetched in "raw" format and go through the same RFC 5322 parser
as the demo mailbox. Drafts are written by a separate class that needs a
separate consent. There is no method that sends mail.
"""

import base64
from datetime import datetime
from typing import Any

from inbox_planner.mail.compose import DraftReply, build_reply
from inbox_planner.mail.models import Message
from inbox_planner.mail.parsing import parse_rfc822

DEFAULT_QUERY = "in:inbox newer_than:14d"


class GmailConnector:
    """Read-only access to a Gmail inbox (scope gmail.readonly)."""

    name = "gmail"

    def __init__(
        self,
        service: Any,
        mailbox: str = "gmail",
        query: str = DEFAULT_QUERY,
        max_messages: int = 100,
    ) -> None:
        self._messages = service.users().messages()
        self.mailbox = mailbox
        self.query = query
        self.max_messages = max_messages

    def _ids(self, query: str) -> list[str]:
        ids: list[str] = []
        page_token = None
        while len(ids) < self.max_messages:
            page = self._messages.list(
                userId="me",
                q=query,
                maxResults=min(100, self.max_messages - len(ids)),
                pageToken=page_token,
            ).execute()
            ids += [item["id"] for item in page.get("messages", [])]
            page_token = page.get("nextPageToken")
            if not page_token:
                break
        return ids[: self.max_messages]

    def fetch_messages(self, since: datetime | None = None) -> list[Message]:
        query = self.query + (f" after:{int(since.timestamp())}" if since else "")
        messages = []
        self.skipped = 0  # malformed e-mails (no date, broken encoding): counted, never fatal
        for gmail_id in self._ids(query):
            item = self._messages.get(userId="me", id=gmail_id, format="raw").execute()
            raw = base64.urlsafe_b64decode(item["raw"].encode("ascii"))
            try:
                message = parse_rfc822(raw, mailbox=self.mailbox, message_id=gmail_id)
            except ValueError:
                self.skipped += 1
                continue
            messages.append(message.model_copy(update={"thread_id": item.get("threadId")}))
        return sorted(messages, key=lambda m: m.sent_at)


class GmailDraftWriter:
    """Saves reviewed replies as Gmail drafts (scope gmail.compose). Never sends."""

    label = "tes brouillons Gmail"  # where approved drafts go, as shown to the user

    def __init__(self, service: Any) -> None:
        self._drafts = service.users().drafts()

    def save(self, original: Message, draft: DraftReply) -> str:
        raw = base64.urlsafe_b64encode(build_reply(original, draft).as_bytes()).decode("ascii")
        message: dict[str, str] = {"raw": raw}
        if original.thread_id:
            message["threadId"] = original.thread_id
        created = self._drafts.create(userId="me", body={"message": message}).execute()
        return str(created["id"])
