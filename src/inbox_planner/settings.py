"""Where real-account files live: always outside the repository.

Everything can be changed with environment variables (see .env.example);
`uv run --env-file .env ...` loads them.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    home: Path

    @property
    def google_client_secret(self) -> Path:  # downloaded from Google Cloud by the user
        default = self.home / "google-client-secret.json"
        return Path(os.environ.get("GOOGLE_CLIENT_SECRET_FILE", default)).expanduser()

    @property
    def tokens(self) -> Path:  # OAuth tokens, readable by the user only
        return self.home / "tokens"

    @property
    def llm_cache(self) -> Path:  # model answers about REAL mail: never in the repository
        return self.home / "llm-cache"


def paths() -> Paths:
    return Paths(
        Path(os.environ.get("INBOX_PLANNER_HOME", Path.home() / ".inbox-planner")).expanduser()
    )


def user_timezone() -> str:
    return os.environ.get("INBOX_PLANNER_TIMEZONE", "America/Los_Angeles")


def map_area() -> str | None:
    """Town added to map searches for places that do not name one (e.g. "Corvallis, OR")."""
    return os.environ.get("INBOX_PLANNER_MAP_AREA") or None
