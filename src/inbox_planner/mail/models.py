"""Provider-independent representation of an e-mail."""

from pydantic import AwareDatetime, BaseModel, ConfigDict


class Message(BaseModel):
    """One e-mail, in the same shape whatever connector it came from."""

    model_config = ConfigDict(frozen=True)

    id: str  # provider id (Gmail id, IMAP UID...) or the Message-ID header
    mailbox: str  # which inbox it came from, e.g. "lyon2", "osu", "personal"
    sender: str  # "Display Name <address>"
    recipients: tuple[str, ...] = ()
    subject: str
    sent_at: AwareDatetime  # a date without a timezone is rejected
    body_text: str
    body_html: str | None = None
