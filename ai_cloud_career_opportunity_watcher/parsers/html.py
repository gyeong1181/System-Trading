from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from core.text import collapse_whitespace


def extract_article_links(
    html: str,
    base_url: str,
    link_pattern: str,
    max_items: int = 20,
) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor.get("href", ""))
        if link_pattern and link_pattern not in href:
            continue
        if href in seen_urls:
            continue

        title = collapse_whitespace(anchor.get_text(" ", strip=True))
        if len(title) < 12:
            continue

        container = anchor.find_parent(["article", "li", "div", "section"])
        time_value = _extract_time_text(container)
        raw_text = collapse_whitespace(container.get_text(" ", strip=True) if container else title)
        results.append(
            {
                "url": href,
                "title": title,
                "raw_text": raw_text,
                "posted_at_text": time_value,
            }
        )
        seen_urls.add(href)
        if len(results) >= max_items:
            break
    return results


def _extract_time_text(container: Tag | None) -> str | None:
    if not container:
        return None
    time_tag = container.find("time")
    if not time_tag:
        return None
    return collapse_whitespace(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))
