"""Link clean-up done in code rather than by the model."""

from urllib.parse import parse_qs, urlsplit

_SAFELINKS_SUFFIX = ".safelinks.protection.outlook.com"


def unwrap_safelinks(url: str) -> str:
    """Return the original URL hidden in an Outlook Safe Links URL; other URLs unchanged."""
    parts = urlsplit(url)
    if (parts.hostname or "").endswith(_SAFELINKS_SUFFIX):
        original = parse_qs(parts.query).get("url")
        if original:
            return original[0]
    return url
