"""SQLite storage for what must survive a restart: the energy chosen for each day.

Everything else on the pages is recomputed from the mailbox and the recorded
answers, so nothing else is stored.
"""

import os
from datetime import date
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine, select

from inbox_planner.planning.energy import Energy

DEFAULT_DB = Path.home() / ".inbox-planner" / "inbox-planner.db"


class EnergyChoice(SQLModel, table=True):
    day: date = Field(primary_key=True)
    energy: Energy


class EnergyStore:
    def __init__(self, url: str) -> None:
        in_memory = url in ("sqlite://", "sqlite:///:memory:")
        self.engine = create_engine(
            url,
            connect_args={"check_same_thread": False},  # FastAPI runs handlers in threads
            poolclass=StaticPool if in_memory else None,
        )
        SQLModel.metadata.create_all(self.engine)

    @classmethod
    def from_env(cls) -> "EnergyStore":
        url = os.environ.get("INBOX_PLANNER_DB")
        if url is None:
            DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{DEFAULT_DB}"
        return cls(url)

    def all(self) -> dict[date, Energy]:
        with Session(self.engine) as session:
            return {c.day: c.energy for c in session.exec(select(EnergyChoice))}

    def set(self, day: date, energy: Energy) -> None:
        with Session(self.engine) as session:
            session.merge(EnergyChoice(day=day, energy=energy))
            session.commit()
