from __future__ import annotations

from app.config import Settings
from collectors.greenhouse_jobs import GreenhouseJobsCollector
from collectors.html_articles import HTMLArticlesCollector
from collectors.html_job_listings import HTMLJobListingsCollector
from collectors.rss_feed import RSSFeedCollector


def build_collector(collector_kind: str, settings: Settings):
    registry = {
        "greenhouse_jobs": GreenhouseJobsCollector,
        "html_articles": HTMLArticlesCollector,
        "html_job_listings": HTMLJobListingsCollector,
        "rss_feed": RSSFeedCollector,
    }
    try:
        return registry[collector_kind](settings)
    except KeyError as exc:
        raise ValueError(f"알 수 없는 collector_kind 입니다: {collector_kind}") from exc
