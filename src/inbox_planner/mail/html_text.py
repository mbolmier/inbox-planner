"""Small HTML-to-text conversion that keeps link targets visible.

HTML-only e-mails (newsletters, Outlook invitations) often hide the useful URL
behind a label such as "Join the meeting". The extraction step needs that URL,
so a link is rendered as ``label <url>``.
"""

from html.parser import HTMLParser

_BLOCK_TAGS = frozenset(
    {"br", "p", "div", "li", "tr", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"}
)
_SKIPPED_TAGS = frozenset({"head", "script", "style", "title"})


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skipped_depth = 0
        self._href: str | None = None
        self._link_label: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skipped_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._link_label = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # <br/> must count once, like <br>.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self._skipped_depth = max(0, self._skipped_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")
        elif tag == "a":
            label = "".join(self._link_label).strip()
            if self._href and self._href not in label:
                self.parts.append(f" <{self._href}>")
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skipped_depth:
            return
        self.parts.append(data)
        if self._href is not None:
            self._link_label.append(data)


def html_to_text(html: str) -> str:
    """Return readable plain text from an HTML body, keeping link URLs."""
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    lines = [" ".join(line.split()) for line in "".join(extractor.parts).splitlines()]
    kept: list[str] = []
    for line in lines:
        # Keep at most one blank line in a row.
        if line or (kept and kept[-1]):
            kept.append(line)
    return "\n".join(kept).strip()
