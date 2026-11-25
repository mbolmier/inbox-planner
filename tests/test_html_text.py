from inbox_planner.mail.html_text import html_to_text


def test_scripts_styles_and_head_are_dropped():
    html = "<html><head><title>T</title><style>p{}</style></head><body><p>Texte</p></body></html>"

    assert html_to_text(html) == "Texte"


def test_line_breaks_count_once_and_blank_lines_are_collapsed():
    html = "Ligne 1<br>Ligne 2<br/>Ligne 3<p></p><p></p><p>Ligne 4</p>"

    assert html_to_text(html) == "Ligne 1\nLigne 2\nLigne 3\n\nLigne 4"


def test_link_url_is_not_repeated_when_the_label_already_shows_it():
    html = '<a href="https://zoom.us/j/1">https://zoom.us/j/1</a>'

    assert html_to_text(html) == "https://zoom.us/j/1"


def test_html_entities_are_decoded():
    assert html_to_text("<p>R&eacute;union &amp; caf&eacute;</p>") == "Réunion & café"
