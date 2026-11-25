"""Gmail, IMAP and reply drafts, with fake services: no network, no account."""

import base64
import re
import stat
from email import message_from_bytes, policy
from email.message import EmailMessage
from pathlib import Path

import pytest
from fakes import FakeLLM, oracle
from fastapi.testclient import TestClient

from inbox_planner.agents.drafting import DraftingAgent, can_reply
from inbox_planner.connectors.base import MailConnector
from inbox_planner.connectors.demo import DEMO_NOW, DEMO_TIMEZONES, DemoConnector
from inbox_planner.connectors.gmail import GmailConnector, GmailDraftWriter
from inbox_planner.connectors.google_auth import GMAIL_READ_SCOPES, save_private_file
from inbox_planner.connectors.imap import ImapConnector, imap_date
from inbox_planner.mail.compose import DraftReply, reply_subject
from inbox_planner.web.app import create_app
from inbox_planner.web.state import AppData
from inbox_planner.web.store import LocalStore

SOURCE = Path(__file__).parents[1] / "src" / "inbox_planner"
MESSAGES = {m.id: m for m in DemoConnector().fetch_messages()}


def raw_mail(subject: str = "Rendez-vous", message_id: str = "<orig@school.example>") -> bytes:
    msg = EmailMessage()
    msg["Message-ID"] = message_id
    msg["From"] = "Dana <dana@school.example>"
    msg["To"] = "Camille <c@school.example>"
    msg["Date"] = "Wed, 21 Oct 2026 10:04:00 -0700"
    msg["Subject"] = subject
    msg["References"] = "<first@school.example>"
    msg.set_content("Bonjour")
    return msg.as_bytes()


# --- the promise: no code path can send an e-mail ----------------------------------


def test_no_code_path_can_send_an_email():
    forbidden = re.compile(
        r"\.send\(|smtplib|sendmail|send_message|messages\(\)\.send|drafts\(\)\.send"
    )
    offenders = [
        str(path.relative_to(SOURCE))
        for path in SOURCE.rglob("*.py")
        if forbidden.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_default_gmail_permission_is_read_only():
    assert GMAIL_READ_SCOPES == ("https://www.googleapis.com/auth/gmail.readonly",)


def test_tokens_are_written_readable_by_their_owner_only(tmp_path):
    token = tmp_path / "tokens" / "gmail.json"

    save_private_file(token, '{"token": "not-real"}')

    assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert stat.S_IMODE(token.parent.stat().st_mode) == 0o700


# --- Gmail (fake API client) -------------------------------------------------------


class FakeGmail:
    """Mimics service.users().messages() and .drafts() of the Gmail API client."""

    def __init__(self, raws: dict[str, bytes]) -> None:
        self.raws = raws
        self.calls: list[tuple[str, dict]] = []

    def users(self):
        return self

    def messages(self):
        return self

    def drafts(self):
        return self

    def _call(self, name: str, result: dict, **kwargs):
        self.calls.append((name, kwargs))
        return type("Request", (), {"execute": lambda _self: result})()

    def list(self, **kwargs):
        return self._call("list", {"messages": [{"id": i} for i in self.raws]}, **kwargs)

    def get(self, **kwargs):
        raw = base64.urlsafe_b64encode(self.raws[kwargs["id"]]).decode()
        return self._call("get", {"raw": raw, "threadId": f"thread-{kwargs['id']}"}, **kwargs)

    def create(self, **kwargs):
        return self._call("create", {"id": "draft-42"}, **kwargs)


def test_gmail_messages_go_through_the_shared_parser():
    gmail = FakeGmail({"g2": raw_mail("Second"), "g1": raw_mail("First")})
    connector = GmailConnector(gmail, mailbox="personal", query="in:inbox")

    messages = connector.fetch_messages()

    assert isinstance(connector, MailConnector)
    assert {m.id for m in messages} == {"g1", "g2"}
    assert messages[0].thread_id.startswith("thread-")
    assert messages[0].header_id == "<orig@school.example>"
    assert all(kwargs.get("format") == "raw" for name, kwargs in gmail.calls if name == "get")
    assert gmail.calls[0][1]["q"] == "in:inbox"


def test_a_malformed_gmail_message_is_skipped_not_fatal():
    broken = b"Subject: no date header\r\n\r\nbody"
    connector = GmailConnector(FakeGmail({"ok": raw_mail(), "bad": broken}))

    messages = connector.fetch_messages()

    assert [m.id for m in messages] == ["ok"]
    assert connector.skipped == 1


def test_gmail_since_becomes_an_after_filter():
    gmail = FakeGmail({})

    GmailConnector(gmail, query="in:inbox").fetch_messages(since=DEMO_NOW)

    assert gmail.calls[0][1]["q"] == f"in:inbox after:{int(DEMO_NOW.timestamp())}"


def test_a_draft_is_created_in_the_thread_and_never_sent():
    original = GmailConnector(FakeGmail({"g1": raw_mail()})).fetch_messages()[0]
    gmail = FakeGmail({})
    draft = DraftReply(
        source_message_id="g1",
        to="Dana <dana@school.example>",
        subject="Re: Rendez-vous",
        body="Merci, c'est noté.",
    )

    draft_id = GmailDraftWriter(gmail).save(original, draft)

    [(name, kwargs)] = gmail.calls
    assert (name, draft_id) == ("create", "draft-42")
    sent = kwargs["body"]["message"]
    assert sent["threadId"] == "thread-g1"
    rebuilt = message_from_bytes(base64.urlsafe_b64decode(sent["raw"]), policy=policy.default)
    assert rebuilt["In-Reply-To"] == "<orig@school.example>"
    assert rebuilt["References"] == "<first@school.example> <orig@school.example>"


def test_reply_subject_is_not_prefixed_twice():
    assert reply_subject("Rendez-vous") == "Re: Rendez-vous"
    assert reply_subject("RE: Rendez-vous") == "RE: Rendez-vous"


# --- IMAP (fake server) --------------------------------------------------------------


class FakeImap:
    def __init__(self, raws: list[bytes]) -> None:
        self.raws = raws
        self.commands: list[tuple] = []

    def login(self, user, password):
        self.commands.append(("login", user))

    def select(self, folder, readonly=False):
        self.commands.append(("select", folder, readonly))
        return "OK", [b"2"]

    def uid(self, command, *args):
        self.commands.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [b" ".join(str(n + 1).encode() for n in range(len(self.raws)))]
        return "OK", [(b"1 (BODY[] {123}", self.raws[int(args[0]) - 1]), b")"]

    def logout(self):
        self.commands.append(("logout",))


def test_imap_opens_the_folder_read_only_and_does_not_mark_mail_as_read():
    server = FakeImap([raw_mail("One"), raw_mail("Two")])
    connector = ImapConnector("imap.example", "u", "p", client_factory=lambda h, p: server)

    messages = connector.fetch_messages()

    assert [m.subject for m in messages] == ["One", "Two"]
    assert ("select", "INBOX", True) in server.commands  # EXAMINE
    fetches = [c for c in server.commands if c[:2] == ("uid", "FETCH")]
    assert fetches and all(c[3] == "(BODY.PEEK[])" for c in fetches)
    assert server.commands[-1] == ("logout",)


def test_imap_dates_use_english_months():
    assert imap_date(DEMO_NOW) == "26-Oct-2026"


# --- drafting agent and human validation -----------------------------------------------


def test_drafting_agent_answers_the_sender_in_the_same_subject():
    agent = DraftingAgent(FakeLLM(oracle), "m", DEMO_TIMEZONES, DEMO_NOW, signature="Camille")

    draft = agent.run(MESSAGES["m02"])

    assert draft.to == "Dana Whitfield <dana.whitfield@oregonstate.example>"
    assert draft.subject == "Re: Exchange student check-in - Thursday, October 29"
    assert "Camille" in agent.system


def test_automated_senders_get_no_reply():
    assert not can_reply(MESSAGES["m08"])  # Canvas notifications
    assert can_reply(MESSAGES["m02"])


@pytest.fixture
def client() -> TestClient:
    data = AppData.demo_mailbox(FakeLLM(oracle))
    return TestClient(create_app(data, LocalStore("sqlite://")))


def test_a_reply_is_only_proposed_until_the_user_saves_it(client):
    htmx = {"HX-Request": "true"}

    proposal = client.post("/mails/m02/reponse", data={"intent": "confirmer"}, headers=htmx)
    assert proposal.status_code == 200
    assert "Enregistrer comme brouillon" in proposal.text and "Rien n'est envoyé" in proposal.text

    form = {
        "to": "Dana <dana@school.example>",
        "subject": "Re: x",
        "body": "Texte relu et modifié.",
    }
    assert client.post("/mails/m02/reponse/enregistrer", data=form).status_code == 403
    saved = client.post("/mails/m02/reponse/enregistrer", data=form, headers=htmx)
    assert saved.status_code == 200
    assert "Il n'a pas été envoyé" in saved.text and "local-1" in saved.text


def test_no_reply_box_for_automated_senders(client):
    assert "Répondre" not in client.get("/mails/m08").text
    assert "Répondre" in client.get("/mails/m02").text
