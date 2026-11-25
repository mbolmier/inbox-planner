"""The contract every mail connector follows."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from inbox_planner.mail.models import Message


@runtime_checkable
class MailConnector(Protocol):
    """Read-only access to one mail source.

    There is deliberately no method to send mail. Draft creation arrives with
    the Gmail connector and will stay a separate, explicit method.
    """

    name: str

    def fetch_messages(self, since: datetime | None = None) -> list[Message]:
        """Return the messages sent at or after ``since``, oldest first."""
        ...
