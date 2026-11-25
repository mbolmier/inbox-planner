"""The read-only copy for GitHub Pages: complete, relative links, nothing that writes."""

import json
import re

import pytest
from fakes import FakeLLM, oracle

from inbox_planner.web.export_site import export_site, relative, rewrite
from inbox_planner.web.state import AppData

DATA = AppData.demo_mailbox(FakeLLM(oracle))


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    output = tmp_path_factory.mktemp("site")
    export_site(output, DATA)
    return output


def test_every_page_mail_and_asset_is_written(site):
    pages = ("index.html", "jours.html", "semaine.html", "echeances.html", "administratif.html")
    for name in pages:
        assert (site / name).is_file()
    assert len(list((site / "mails").glob("*.html"))) == len(DATA.processed)
    assert (site / "static" / "week.js").is_file() and (site / "static" / "style.css").is_file()
    assert (site / "export.ics").read_bytes().startswith(b"BEGIN:VCALENDAR")


def test_links_are_relative_so_the_site_works_under_any_address(site):
    for page in [*site.glob("*.html"), *(site / "mails").glob("*.html")]:
        html = page.read_text()
        assert not re.search(r'\s(?:href|src|data-events)="/(?!/)', html), page.name
    assert 'href="../index.html"' in (site / "mails" / "m18.html").read_text()
    assert 'data-events="api/calendrier.json"' in (site / "semaine.html").read_text()


def test_the_calendar_feed_links_to_the_static_mail_pages(site):
    feed = json.loads((site / "api" / "calendrier.json").read_text())

    links = {e["extendedProps"].get("mail") for e in feed} - {None}
    assert links and all(re.fullmatch(r"mails/m\d\d\.html", link) for link in links)


def test_the_copy_says_it_is_read_only_and_disables_what_writes(site):
    days = (site / "jours.html").read_text()

    assert "Version en ligne, en lecture seule" in days
    assert 'http-equiv="Content-Security-Policy"' in days  # no headers on GitHub Pages
    checkboxes = re.findall(r'<input type="checkbox"[^>]*>', days)
    assert checkboxes and all("disabled" in box for box in checkboxes)
    assert all("disabled" in s for s in re.findall(r"<select[^>]*>", days))


def test_rewrite_only_touches_the_app_paths():
    html = (
        '<a href="/jours">x</a> <a href="https://example.com/a">y</a> <script src="//cdn.x/y.js">'
    )

    assert rewrite(html, 1) == (
        '<a href="../jours.html">x</a> <a href="https://example.com/a">y</a> '
        '<script src="//cdn.x/y.js">'
    )
    assert relative("/mails/m01/reponse", 0) == "/mails/m01/reponse"  # not exported: unchanged
