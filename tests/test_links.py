from inbox_planner.mail.links import unwrap_safelinks


def test_safe_link_gives_back_the_original_url():
    wrapped = (
        "https://nam12.safelinks.protection.outlook.com/?url=https%3A%2F%2Fzoom.us%2Fj%2F123&data=x"
    )

    assert unwrap_safelinks(wrapped) == "https://zoom.us/j/123"


def test_other_urls_are_unchanged():
    assert (
        unwrap_safelinks("https://meet.google.com/abc-defg-hij")
        == "https://meet.google.com/abc-defg-hij"
    )
