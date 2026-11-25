"""Clickable places: a physical place opens Google Maps, an online one opens the meeting.

No API key is needed: Google Maps' documented search URL (api=1) only takes a
query. Only https links are ever turned into a clickable meeting link: a mail
could carry a `javascript:` link that would run code when clicked in the app.
"""

from dataclasses import dataclass
from urllib.parse import quote_plus, urlsplit

from inbox_planner.mail.links import unwrap_safelinks

VIDEO_PROVIDERS = (
    ("zoom.us", "Zoom"),
    ("teams.microsoft.com", "Microsoft Teams"),
    ("teams.live.com", "Microsoft Teams"),
    ("meet.google.com", "Google Meet"),
)
MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query="


@dataclass(frozen=True)
class Place:
    online: bool
    label: str  # what is shown: the provider, or the place as written in the mail
    url: str
    meeting_id: str | None = None
    passcode: str | None = None


def video_provider(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    for domain, name in VIDEO_PROVIDERS:
        if host == domain or host.endswith("." + domain):
            return name
    return "Visio"


def is_safe_link(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.hostname)


def maps_url(location: str, area: str | None = None) -> str:
    """Google Maps search; the mailbox's area is added when the place does not name it."""
    query = location if not area or area.lower() in location.lower() else f"{location}, {area}"
    return MAPS_SEARCH + quote_plus(query)


def resolve_place(
    location: str | None,
    video_url: str | None,
    meeting_id: str | None = None,
    passcode: str | None = None,
    area: str | None = None,
) -> Place | None:
    if video_url:
        url = unwrap_safelinks(video_url)
        if is_safe_link(url):
            return Place(True, video_provider(url), url, meeting_id, passcode)
    if location:
        return Place(False, location, maps_url(location, area))
    return None
