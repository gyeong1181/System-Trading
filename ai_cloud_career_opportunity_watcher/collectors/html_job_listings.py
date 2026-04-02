from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors.base import BaseCollector
from core.schemas import CollectedItem
from core.text import collapse_whitespace, split_keywords


class HTMLJobListingsCollector(BaseCollector):
    def collect(self, source) -> list[CollectedItem]:
        config = source.config_json or {}
        item_selector = config.get("item_selector", "a[href]")
        title_selector = config.get("title_selector")
        location_selector = config.get("location_selector")
        raw_text_selector = config.get("raw_text_selector")
        link_selector = config.get("link_selector")
        link_pattern = config.get("link_pattern", "")
        max_items = int(config.get("max_items", self.settings.max_source_items))
        required_keywords = [keyword.lower() for keyword in config.get("required_keywords", [])]
        company_name = config.get("company_name", source.name)
        source_urls = config.get("url_overrides") or [source.url]

        items: list[CollectedItem] = []
        seen_urls: set[str] = set()

        for source_url in source_urls:
            html = self.fetch_text(source_url)
            soup = BeautifulSoup(html, "html.parser")

            for node in soup.select(item_selector):
                link_node = node.select_one(link_selector) if link_selector else node
                href = link_node.get("href") if link_node else None
                if not href:
                    continue
                absolute_url = urljoin(source_url, href)
                if link_pattern and link_pattern not in absolute_url:
                    continue
                if absolute_url in seen_urls:
                    continue

                title = _extract_text(node, title_selector) if title_selector else collapse_whitespace(node.get_text(" ", strip=True))
                if len(title) < 8:
                    continue

                location = _extract_text(node, location_selector) if location_selector else None
                raw_text = _extract_text(node, raw_text_selector) if raw_text_selector else collapse_whitespace(node.get_text(" ", strip=True))
                searchable = " ".join([title, location or "", raw_text]).lower()

                if required_keywords and not any(keyword in searchable for keyword in required_keywords):
                    continue

                items.append(
                    CollectedItem(
                        source_type=source.source_type,
                        source_name=source.name,
                        title=title,
                        company_name=company_name,
                        url=absolute_url,
                        location=location,
                        role=config.get("default_role"),
                        tech_stack=split_keywords(searchable, required_keywords),
                        raw_text=raw_text,
                        posted_at=_parse_datetime(_extract_text(node, "time")),
                    )
                )
                seen_urls.add(absolute_url)
                if len(items) >= max_items:
                    return items

        return items


def _extract_text(node, selector: str | None) -> str | None:
    if not selector:
        return None
    target = node.select_one(selector)
    if target is None:
        return None
    return collapse_whitespace(target.get_text(" ", strip=True))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
