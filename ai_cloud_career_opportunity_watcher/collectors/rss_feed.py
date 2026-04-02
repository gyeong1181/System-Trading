from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

from collectors.base import BaseCollector
from core.schemas import CollectedItem
from parsers.rss import parse_rss_entries


class RSSFeedCollector(BaseCollector):
    def collect(self, source) -> list[CollectedItem]:
        config = source.config_json or {}
        max_items = int(config.get("max_items", self.settings.max_source_items))
        xml_text = self.fetch_text(source.url)
        entries = parse_rss_entries(xml_text)

        items: list[CollectedItem] = []
        for entry in entries[:max_items]:
            items.append(
                CollectedItem(
                    source_type=source.source_type,
                    source_name=source.name,
                    title=str(entry["title"]),
                    company_name=config.get("company_name", source.name),
                    url=str(entry["url"]),
                    raw_text=str(entry["raw_text"]),
                    posted_at=_parse_datetime(entry.get("posted_at_text")),
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
