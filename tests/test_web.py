"""Web pages, run on the perfect fake model (no recordings needed)."""

from dataclasses import replace

import pytest
from fakes import FakeLLM, oracle
from fastapi.testclient import TestClient

from inbox_planner.web.app import create_app
from inbox_planner.web.state import AppData
from inbox_planner.web.store import LocalStore

DATA = AppData.demo_mailbox(FakeLLM(oracle))
HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(DATA, LocalStore("sqlite://")))


@pytest.mark.parametrize(
    "path", ["/", "/semaine", "/echeances", "/mails/m02", "/api/calendrier", "/export.ics"]
)
def test_every_page_answers_with_security_headers(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert (
        "script-src 'self' https://cdn.jsdelivr.net" in response.headers["content-security-policy"]
    )
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_today_shows_both_clocks_the_day_and_a_map_link(client):
    html = client.get("/").text

    assert "Lundi 26 octobre" in html
    assert '<b>Paris</b> <time class="mono">16:00</time> <small>+8 h</small>' in html
    assert (
        "https://www.google.com/maps/search/?api=1&amp;query=Alder+Hall+120%2C+Corvallis%2C+OR"
        in html
    )


def test_cdn_scripts_are_pinned_with_an_integrity_hash(client):
    for path in ("/", "/semaine"):
        html = client.get(path).text
        assert 'src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.11/dist/htmx.min.js"' in html
        assert html.count('integrity="sha256-') == html.count('src="https://cdn.jsdelivr.net')


def test_changing_the_energy_requires_htmx_then_replans_and_is_remembered(client):
    form = {"energy": "tired", "view": "today"}

    assert client.post("/energie/2026-10-26", data=form).status_code == 403
    response = client.post("/energie/2026-10-26", data=form, headers=HTMX)

    assert response.status_code == 200
    assert 'aria-pressed="true">Crevé</button>' in response.text
    assert "Prévu aujourd'hui : <b>1 h</b>" in response.text  # only what is due today
    assert 'aria-pressed="true">Crevé</button>' in client.get("/").text


def test_a_change_in_the_week_view_tells_the_calendar_to_reload(client):
    response = client.post(
        "/energie/2026-10-27", data={"energy": "off", "view": "week"}, headers=HTMX
    )

    assert response.headers["hx-trigger"] == "planChanged"
    assert 'id="week-energy"' in response.text
    assert 'aria-label="Énergie du Mardi 27/10"' in response.text  # screen readers hear the day


def test_a_day_outside_the_planned_week_is_refused(client):
    response = client.post("/energie/2027-01-01", data={"energy": "off"}, headers=HTMX)

    assert response.status_code == 404


def test_mail_text_is_shown_escaped_never_as_html():
    original = DATA.processed["m11"]
    trapped = replace(
        original,
        message=original.message.model_copy(
            update={"body_text": '<script>alert("pwned")</script><img src=x onerror=1>'}
        ),
    )
    data = replace(DATA, processed=DATA.processed | {"m11": trapped})
    html = TestClient(create_app(data, LocalStore("sqlite://"))).get("/mails/m11").text

    assert "&lt;script&gt;alert(&#34;pwned&#34;)&lt;/script&gt;" in html
    assert "<script>alert" not in html and "<img src=x" not in html


def test_an_unknown_mail_is_a_404(client):
    assert client.get("/mails/does-not-exist").status_code == 404


def test_calendar_feed_gives_oregon_wall_clock_times_without_offset(client):
    feed = client.get("/api/calendrier").json()

    deadlines = [e for e in feed if e["title"].startswith("Échéance : ")]
    assert deadlines and all("end" not in e for e in deadlines)  # an instant, never past midnight
    hike, session = (e for e in feed if e.get("url") == "/mails/m39")
    assert (hike["start"], hike["end"]) == ("2026-10-31T07:30:00", "2026-10-31T16:00:00")
    # After the 1 November change (-07:00 to -08:00), 14:00 stays 14:00 on the wall clock.
    assert (session["start"], session["end"]) == ("2026-11-01T14:00:00", "2026-11-01T17:00:00")
    assert all("+" not in e["start"] and not e["start"].endswith("Z") for e in feed)


def test_ics_download_with_and_without_planned_work(client):
    plain = client.get("/export.ics")
    with_work = client.get("/export.ics?travail=true")

    assert plain.headers["content-type"].startswith("text/calendar")
    assert 'filename="inbox-planner.ics"' in plain.headers["content-disposition"]
    assert plain.text.startswith("BEGIN:VCALENDAR")
    assert "Travail :" not in plain.text and "Travail :" in with_work.text


# --- links inside e-mails ---------------------------------------------------------

from inbox_planner.web.links import linkify, short_url  # noqa: E402

SAFE_LINK = (
    "https://eur03.safelinks.protection.outlook.com/?url=https%3A%2F%2Fteams.microsoft.com"
    "%2Fl%2Fmeetup-join%2F19%253ameeting_abc%2540thread.v2%2F0&data=05&reserved=0"
)


def test_long_links_are_short_clickable_and_unwrapped():
    html = str(linkify(f"Rejoindre la réunion maintenant <{SAFE_LINK}>"))

    assert 'class="mail-link" href="https://teams.microsoft.com/l/meetup-join/' in html
    assert ">teams.microsoft.com/l/meetup-join/19%3am" in html and "…</a>" in html
    assert "<code>https://teams.microsoft.com/l/meetup-join/" in html  # full link = real one
    assert "safelinks" not in html.split("<code>")[1]
    assert "&lt;https" not in html  # Outlook's angle brackets removed


def test_only_https_links_become_clickable_and_text_stays_escaped():
    html = str(linkify("<b>x</b> http://plain.example/a javascript:alert(1) https://zoom.us/j/1."))

    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert 'href="http://plain.example' not in html and "javascript:alert(1)" in html
    assert 'href="https://zoom.us/j/1"' in html and html.endswith("</a>.")


def test_short_url_keeps_host_and_start_of_path():
    assert short_url("https://www.example.org/") == "example.org"
    assert len(short_url("https://zoom.us/j/" + "9" * 80)) == 42


def test_mail_page_shows_the_meeting_link_short(client):
    html = client.get("/mails/m18").text

    assert 'class="mail-link" href="https://teams.microsoft.com/' in html
    assert ">eur03.safelinks" not in html  # the long wrapper is never the visible text
