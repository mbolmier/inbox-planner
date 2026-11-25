from datetime import UTC, datetime

import pytest

from inbox_planner.connectors.base import MailConnector
from inbox_planner.connectors.demo import DEMO_NOW, DemoConnector

MAILBOXES = {"lyon2", "osu", "personal"}


def test_demo_connector_follows_the_connector_contract():
    assert isinstance(DemoConnector(), MailConnector)


def test_demo_mailbox_loads_oldest_first_with_timezone_aware_dates():
    messages = DemoConnector().fetch_messages()

    assert messages, "the demo mailbox must not be empty"
    assert [m.sent_at for m in messages] == sorted(m.sent_at for m in messages)
    assert all(m.sent_at.tzinfo is not None for m in messages)
    assert {m.mailbox for m in messages} <= MAILBOXES


def test_demo_message_ids_are_unique():
    ids = [m.id for m in DemoConnector().fetch_messages()]

    assert len(ids) == len(set(ids))


def test_every_demo_message_was_sent_before_the_frozen_demo_clock():
    assert all(m.sent_at <= DEMO_NOW for m in DemoConnector().fetch_messages())


def test_since_keeps_only_newer_messages():
    cutoff = datetime(2026, 10, 22, tzinfo=UTC)
    every = DemoConnector().fetch_messages()
    recent = DemoConnector().fetch_messages(since=cutoff)

    assert all(m.sent_at >= cutoff for m in recent)
    assert len(recent) == sum(m.sent_at >= cutoff for m in every)


def test_accents_survive_the_round_trip_through_mime(tmp_path):
    mailbox = tmp_path / "mailbox.toml"
    mailbox.write_text(
        "[[message]]\n"
        'id = "t1"\nmailbox = "lyon2"\n'
        'from = "Scolarité <s@univ.example>"\nto = "Camille <c@etu.example>"\n'
        "date = 2026-10-26T08:15:00+01:00\n"
        'subject = "Échéance à noter"\ntext = "Dépôt avant vendredi."\n',
        encoding="utf-8",
    )
    [message] = DemoConnector(mailbox).fetch_messages()

    assert message.sender == "Scolarité <s@univ.example>"
    assert message.subject == "Échéance à noter"
    assert message.body_text == "Dépôt avant vendredi."


def test_a_demo_date_without_utc_offset_is_rejected(tmp_path):
    mailbox = tmp_path / "mailbox.toml"
    mailbox.write_text(
        "[[message]]\n"
        'id = "t1"\nmailbox = "osu"\nfrom = "a <a@b.example>"\nto = "c <c@d.example>"\n'
        'date = 2026-10-26T08:00:00\nsubject = "s"\ntext = "t"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="offset"):
        DemoConnector(mailbox).fetch_messages()
