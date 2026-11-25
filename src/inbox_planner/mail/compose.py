"""Build a reply draft as a real e-mail, in the same thread as the original."""

from email.message import EmailMessage
from email.utils import formatdate, getaddresses

from pydantic import BaseModel, ConfigDict

from inbox_planner.mail.models import Message


class DraftReply(BaseModel):
    """A reply proposed by the drafting agent, then reviewed by the user."""

    model_config = ConfigDict(frozen=True)

    source_message_id: str  # the e-mail being answered (provider id)
    to: str
    subject: str
    body: str


def reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith(("re:", "re :")) else f"Re: {subject}"


def reply_to_address(message: Message) -> str:
    """The sender of the original e-mail, as "Name <address>"."""
    [(name, address)] = getaddresses([message.sender]) or [("", "")]
    return f"{name} <{address}>" if name else address


def build_reply(original: Message, draft: DraftReply) -> EmailMessage:
    """The draft as an RFC 5322 e-mail, threaded with In-Reply-To and References."""
    reply = EmailMessage()
    reply["To"] = draft.to
    reply["Subject"] = draft.subject
    reply["Date"] = formatdate(localtime=False)
    if original.header_id:
        reply["In-Reply-To"] = original.header_id
        reply["References"] = " ".join([*original.references, original.header_id])
    reply.set_content(draft.body)
    return reply
