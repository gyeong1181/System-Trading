from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

from collectors.base import BaseCollector
from core.schemas import CollectedItem
from parsers.html import extract_article_links


class HTMLArticlesCollector(BaseCollector):
    def collect(self, source) -> list[CollectedItem]:
        config = source.config_json or {}
        link_pattern = config.get("link_pattern", "")
        max_items = int(config.get("max_items", self.settings.max_source_items))
        html = self.fetch_text(source.url)
        articles = extract_article_links(html, source.url, link_pattern, max_items=max_items)

        items: list[CollectedItem] = []
        for article in articles:
            items.append(
                CollectedItem(
                    source_type=source.source_type,
                    source_name=source.name,
                    title=str(article["title"]),
                    company_name=config.get("company_name", source.name),
                    url=str(article["url"]),
                    raw_text=str(article["raw_text"]),
                    posted_at=_parse_datetime(article.get("posted_at_text")),
                )
            )
        return items


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
