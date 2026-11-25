"""Readable links inside e-mail text.

The text is always escaped. Only https links become clickable; Outlook Safe
Links are unwrapped; the visible text is short (host + start of the path), and
the full address stays available on demand.
"""

import re
from urllib.parse import urlsplit

from markupsafe import Markup, escape

from inbox_planner.locations import is_safe_link
from inbox_planner.mail.links import unwrap_safelinks

# A URL, optionally wrapped in angle brackets as Outlook writes them: <https://...>
URL = re.compile(r"<?(https?://[^\s<>\"']+)>?")
TRAILING = ".,;:!?)"
SHORT_LENGTH = 42


def short_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    rest = parts.path + (f"?{parts.query}" if parts.query else "")
    text = host + (rest if rest not in ("", "/") else "")
    return text if len(text) <= SHORT_LENGTH else text[: SHORT_LENGTH - 1] + "…"


def _link(raw: str) -> Markup:
    target = unwrap_safelinks(raw)
    if not is_safe_link(target):
        return escape(raw)
    short = short_url(target)
    link = Markup(
        '<a class="mail-link" href="{0}" target="_blank" rel="noopener noreferrer" '
        'title="{0}">{1}</a>'
    ).format(target, short)
    if raw != target or len(target) > SHORT_LENGTH:
        note = " (déballé du lien de sécurité Outlook)" if raw != target else ""
        link += Markup(
            '<details class="full-url"><summary>lien complet</summary><code>{0}</code>{1}</details>'
        ).format(target, note)
    return link


def linkify(text: str) -> Markup:
    pieces: list[Markup] = []
    last = 0
    for match in URL.finditer(text):
        url = match.group(1)
        stripped = url.rstrip(TRAILING)
        trailing = url[len(stripped) :]
        pieces.append(escape(text[last : match.start()]))
        pieces.append(_link(stripped))
        pieces.append(escape(trailing))
        last = match.end()
    pieces.append(escape(text[last:]))
    return Markup("").join(pieces)
