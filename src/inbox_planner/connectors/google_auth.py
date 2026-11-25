"""Gmail sign-in (OAuth 2.0, installed-app flow).

The user signs in in their own browser: this program never sees the password.
The token stays on this computer, in a file only the user can read.

Two separate tokens, two levels of consent:
- reading (gmail.readonly), the default;
- drafts (gmail.compose), only if the user turns that feature on. Gmail has no
  "drafts only" scope: gmail.compose would technically allow sending. This
  project never sends (no code path does, and a test guards that).
"""

import os
from pathlib import Path
from typing import Any

GMAIL_READ_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)
GMAIL_DRAFT_SCOPES = ("https://www.googleapis.com/auth/gmail.compose",)


class ConnectorAuthError(Exception):
    """Not signed in, consent missing, or OAuth client file missing."""


def save_private_file(path: Path, content: str) -> None:
    """Write a file readable and writable by its owner only (mode 600)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o600)


def gmail_credentials(
    scopes: tuple[str, ...],
    token_path: Path,
    client_secret_path: Path,
    allow_browser: bool = True,
) -> Any:
    """Return valid credentials: saved token, refreshed token, or a new sign-in."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials = None
    if token_path.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_path), list(scopes))
    if credentials and credentials.valid:
        return credentials
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            save_private_file(token_path, credentials.to_json())
            return credentials
        except RefreshError:
            credentials = None  # apps "in testing" get tokens that expire after 7 days
    if not allow_browser:
        raise ConnectorAuthError("not signed in to Gmail: run `inbox-planner gmail login`")
    if not client_secret_path.is_file():
        raise ConnectorAuthError(f"OAuth client file not found: {client_secret_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), list(scopes))
    credentials = flow.run_local_server(host="localhost", port=0, open_browser=True)
    granted = set(credentials.scopes or ())
    if not set(scopes) <= granted:
        raise ConnectorAuthError("the requested Gmail permission was not granted")
    save_private_file(token_path, credentials.to_json())
    return credentials


def gmail_service(credentials: Any) -> Any:
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=credentials, cache_discovery=False)
