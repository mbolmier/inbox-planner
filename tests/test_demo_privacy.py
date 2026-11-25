"""Privacy guard: the demo data may only contain invented contact details.

Every e-mail address must use a reserved ``.example`` domain (RFC 2606), and
every link must point to an ``.example`` domain or to a video-call provider
(with a made-up meeting id). The rule is checked on every commit by the CI.
"""

import re
from urllib.parse import urlsplit

from inbox_planner.connectors.demo import DEFAULT_MAILBOX

EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"https?://[^\s<>\"')]+")
VIDEO_CALL_HOSTS = ("zoom.us", "teams.microsoft.com", "meet.google.com")

DEMO_FILES = [DEFAULT_MAILBOX]


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
    sample = "Write to jane@oregonstate.edu or see https://www.univ-lyon2.fr/scolarite"

    assert real_looking_addresses(sample) == ["jane@oregonstate.edu"]
    assert disallowed_link_hosts(sample) == ["www.univ-lyon2.fr"]


def test_demo_addresses_use_reserved_example_domains():
    for path in DEMO_FILES:
        assert real_looking_addresses(path.read_text(encoding="utf-8")) == [], path.name


def test_demo_links_point_to_example_domains_or_video_call_providers():
    for path in DEMO_FILES:
        assert disallowed_link_hosts(path.read_text(encoding="utf-8")) == [], path.name
