from __future__ import annotations

from xml.etree import ElementTree

from core.text import strip_html


def parse_rss_entries(xml_text: str) -> list[dict[str, str | None]]:
    root = ElementTree.fromstring(xml_text)
    entries: list[dict[str, str | None]] = []

    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link")
        description = strip_html(_text(item, "description"))
        pub_date = _text(item, "pubDate")
        if not title or not link:
            continue
        entries.append(
            {
                "title": title,
                "url": link,
                "raw_text": description,
                "posted_at_text": pub_date,
            }
        )
    return entries


def _text(item: ElementTree.Element, tag: str) -> str | None:
    element = item.find(tag)
    if element is None or element.text is None:
        return None
    return element.text.strip()
