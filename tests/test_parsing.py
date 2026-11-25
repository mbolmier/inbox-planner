from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from pydantic import ValidationError

from inbox_planner.mail.models import Message
from inbox_planner.mail.parsing import parse_rfc822


def make_email(
    *,
    date: str | None = "Mon, 26 Oct 2026 08:15:00 +0100",
    subject: str = "Sujet",
    text: str | None = "Bonjour",
    html: str | None = None,
) -> bytes:
    msg = EmailMessage()
    msg["Message-ID"] = "<abc@test.example>"
    msg["From"] = "Prof <prof@school.example>"
    msg["To"] = "Camille <camille@school.example>"
    if date is not None:
        msg["Date"] = date
    msg["Subject"] = subject
    if text is not None:
        msg.set_content(text)
        if html is not None:
            msg.add_alternative(html, subtype="html")
    elif html is not None:
        msg.set_content(html, subtype="html")
    return msg.as_bytes()


def test_headers_are_parsed_and_the_utc_offset_is_kept():
    message = parse_rfc822(make_email(), mailbox="lyon2")

    assert message.id == "abc@test.example"
    assert message.mailbox == "lyon2"
    assert message.sender == "Prof <prof@school.example>"
    assert message.recipients == ("Camille <camille@school.example>",)
    assert message.sent_at == datetime(2026, 10, 26, 7, 15, tzinfo=UTC)
    assert message.sent_at.utcoffset() == timedelta(hours=1)


def test_accented_subject_survives_mime_encoding():
    raw = make_email(subject="Échéance : dépôt du dossier")

    assert b"=?utf-8?" in raw.lower()  # really encoded on the wire
    assert parse_rfc822(raw, mailbox="lyon2").subject == "Échéance : dépôt du dossier"


def test_plain_text_part_is_preferred_over_html():
    raw = make_email(text="Version texte", html="<p>Version HTML</p>")
    message = parse_rfc822(raw, mailbox="osu")

    assert message.body_text == "Version texte"
    assert message.body_html is not None and "Version HTML" in message.body_html


def test_html_only_mail_gets_a_text_body_that_keeps_link_targets():
    html = (
        "<p>Réunion de suivi</p>"
        '<p><a href="https://teams.microsoft.com/l/meetup-join/xyz">Rejoindre la réunion</a></p>'
    )
    message = parse_rfc822(make_email(text=None, html=html), mailbox="osu")

    assert message.body_text == (
        "Réunion de suivi\n\nRejoindre la réunion <https://teams.microsoft.com/l/meetup-join/xyz>"
    )


def test_date_without_zone_is_read_as_utc():
    message = parse_rfc822(make_email(date="Mon, 26 Oct 2026 08:15:00 -0000"), mailbox="x")

    assert message.sent_at == datetime(2026, 10, 26, 8, 15, tzinfo=UTC)


def test_mail_without_date_is_rejected():
    with pytest.raises(ValueError, match="Date"):
        parse_rfc822(make_email(date=None), mailbox="x")


def test_provider_id_wins_over_the_message_id_header():
    message = parse_rfc822(make_email(), mailbox="personal", message_id="gmail-18c2f")

    assert message.id == "gmail-18c2f"


def test_message_refuses_a_date_without_timezone():
    with pytest.raises(ValidationError):
        Message(
            id="x",
            mailbox="osu",
            sender="a <a@b.example>",
            subject="s",
            sent_at=datetime(2026, 10, 26, 8, 0),
            body_text="",
        )
