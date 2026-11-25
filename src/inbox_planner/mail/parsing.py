"""Parse raw RFC 5322 e-mails into Message objects.

Every connector ends up here: IMAP and Gmail return raw RFC 5322 bytes, and the
demo connector builds the same bytes from its fictional mailbox. One parser
means one place to handle encodings, multipart bodies and dates.
"""

from datetime import UTC
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import cast

from inbox_planner.mail.html_text import html_to_text
from inbox_planner.mail.models import Message


def parse_rfc822(raw: bytes, *, mailbox: str, message_id: str | None = None) -> Message:
    """Build a Message from raw e-mail bytes.

    ``message_id`` is the provider's own identifier (Gmail id, IMAP UID...).
    Without it, the Message-ID header is used.
    """
    msg = cast(EmailMessage, message_from_bytes(raw, policy=policy.default))

    sent_at = getattr(msg["Date"], "datetime", None)
    if sent_at is None:
        raise ValueError("e-mail has no valid Date header")
    if sent_at.tzinfo is None:
        # "-0000" means UTC with an unknown local zone (RFC 5322, section 3.3).
        sent_at = sent_at.replace(tzinfo=UTC)

    header_id = str(msg["Message-ID"] or "").strip() or None
    resolved_id = message_id or (header_id or "").strip("<>")
    if not resolved_id:
        raise ValueError("e-mail has no identifier")

    plain_part = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    body_html = html_part.get_content() if html_part is not None else None
    if plain_part is not None:
        body_text = plain_part.get_content()
    elif body_html is not None:
        body_text = html_to_text(body_html)
    else:
        body_text = ""

    return Message(
        id=resolved_id,
        mailbox=mailbox,
        sender=str(msg["From"] or ""),
        recipients=_addresses(msg, "To") + _addresses(msg, "Cc"),
        subject=str(msg["Subject"] or ""),
        sent_at=sent_at,
        body_text=body_text.strip(),
        body_html=body_html,
        header_id=header_id,
        references=tuple(str(msg["References"] or "").split()),
    )


def _addresses(msg: EmailMessage, header: str) -> tuple[str, ...]:
    return tuple(str(address) for address in getattr(msg[header], "addresses", ()))
