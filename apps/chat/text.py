"""Plain-text preview helper for rich-text (TipTap HTML) message bodies."""
import html as html_module
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html_preview(body: str, length: int = 140) -> str:
    """Strip HTML tags and collapse whitespace, for notification/push preview
    text — those need plain text, not the rich-formatted body the chat
    thread itself renders."""
    plain = _WHITESPACE_RE.sub(" ", _TAG_RE.sub(" ", html_module.unescape(body or ""))).strip()
    return plain[:length]
