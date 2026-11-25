"""Privacy guard: the demo data may only contain invented contact details.

Every e-mail address must use a reserved ``.example`` domain (RFC 2606), and
every link must point to an ``.example`` domain or to a video-call provider
(with a made-up meeting id), possibly wrapped by Outlook Safe Links. The rule is
checked on every commit by the CI.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

from inbox_planner.connectors.demo import DEFAULT_MAILBOX
from inbox_planner.evaluation.labels import DEFAULT_LABELS
from inbox_planner.llm.cache import DEMO_CACHE

EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"https?://[^\s<>\"')]+")
VIDEO_CALL_HOSTS = (
    "zoom.us",
    "teams.microsoft.com",
    "meet.google.com",
    "safelinks.protection.outlook.com",
)

# The recorded model answers are checked too: a model could invent an address.
DEMO_FILES = [DEFAULT_MAILBOX, DEFAULT_LABELS, *sorted(Path(str(DEMO_CACHE)).rglob("*.json"))]


def real_looking_addresses(text: str) -> list[str]:
    return [a for a in EMAIL_ADDRESS.findall(text) if not a.lower().endswith(".example")]


def disallowed_link_hosts(text: str) -> list[str]:
    hosts = {(urlsplit(url).hostname or "").lower() for url in URL.findall(text)}
    return sorted(
        host
        for host in hosts
        if not host.endswith(".example")
        and not any(host == h or host.endswith("." + h) for h in VIDEO_CALL_HOSTS)
    )


def test_guard_catches_real_addresses_and_links():
    sample = "Write to someone@example.com or see https://www.example.org/scolarite"

    assert real_looking_addresses(sample) == ["someone@example.com"]
    assert disallowed_link_hosts(sample) == ["www.example.org"]


def test_demo_addresses_use_reserved_example_domains():
    for path in DEMO_FILES:
        assert real_looking_addresses(path.read_text(encoding="utf-8")) == [], path.name


def test_demo_links_point_to_example_domains_or_video_call_providers():
    for path in DEMO_FILES:
        assert disallowed_link_hosts(path.read_text(encoding="utf-8")) == [], path.name
