"""SQLite storage for what must survive a restart: the energy chosen for each day,
and, in the demo, the reply drafts the user approved (with a real mailbox they
go to the mailbox's own drafts instead).

Everything else on the pages is recomputed from the mailbox and the recorded
answers, so nothing else is stored.
"""

import os
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine, select

from inbox_planner.mail.compose import DraftReply
from inbox_planner.mail.models import Message
from inbox_planner.planning.energy import Energy

DEFAULT_DB = Path.home() / ".inbox-planner" / "inbox-planner.db"


class EnergyChoice(SQLModel, table=True):
    day: date = Field(primary_key=True)
    energy: Energy


class SavedDraft(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_message_id: str
    to: str
    subject: str
    body: str
    saved_at: datetime


class LocalStore:
    label = "cet ordinateur (démo)"  # where approved drafts go, as shown to the user

    def __init__(self, url: str) -> None:
        in_memory = url in ("sqlite://", "sqlite:///:memory:")
        self.engine = create_engine(
            url,
            connect_args={"check_same_thread": False},  # FastAPI runs handlers in threads
            poolclass=StaticPool if in_memory else None,
        )
        SQLModel.metadata.create_all(self.engine)

    @classmethod
    def from_env(cls) -> "LocalStore":
        url = os.environ.get("INBOX_PLANNER_DB")
        if url is None:
            DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{DEFAULT_DB}"
        return cls(url)

    def energies(self) -> dict[date, Energy]:
        with Session(self.engine) as session:
            return {c.day: c.energy for c in session.exec(select(EnergyChoice))}

    def set_energy(self, day: date, energy: Energy) -> None:
        with Session(self.engine) as session:
            session.merge(EnergyChoice(day=day, energy=energy))
            session.commit()

    def save(self, original: Message, draft: DraftReply) -> str:
        """Keep an approved draft locally (demo). Nothing is sent anywhere."""
        record = SavedDraft(
            source_message_id=original.id,
            to=draft.to,
            subject=draft.subject,
            body=draft.body,
            saved_at=datetime.now(UTC),
        )
        with Session(self.engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return f"local-{record.id}"
