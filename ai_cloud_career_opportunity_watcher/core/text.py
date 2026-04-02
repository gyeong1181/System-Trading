from __future__ import annotations

import re
from html import unescape

from bs4 import BeautifulSoup


WHITESPACE_RE = re.compile(r"\s+")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    return collapse_whitespace(unescape(soup.get_text(" ", strip=True)))


def collapse_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def split_keywords(value: str, keywords: list[str]) -> list[str]:
    haystack = value.lower()
    return [keyword for keyword in keywords if keyword.lower() in haystack]
