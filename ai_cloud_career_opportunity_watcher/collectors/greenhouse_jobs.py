from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

from collectors.base import BaseCollector
from core.schemas import CollectedItem
from core.text import split_keywords, strip_html


class GreenhouseJobsCollector(BaseCollector):
    def collect(self, source) -> list[CollectedItem]:
        config = source.config_json or {}
        board_token = config["board_token"]
        candidate_urls = [
            f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true",
            f"https://api.greenhouse.io/v1/boards/{board_token}/jobs?content=true",
        ]

        payload = None
        for candidate_url in candidate_urls:
            try:
                payload = self.fetch_json(candidate_url)
                break
            except Exception as exc:
                self.logger.warning("Greenhouse 수집 실패(%s): %s", candidate_url, exc)

        if payload is None:
            raise RuntimeError(f"Greenhouse board를 가져오지 못했습니다: {board_token}")

        jobs = payload.get("jobs", [])
        location_keywords = [keyword.lower() for keyword in config.get("location_keywords", [])]
        required_keywords = [keyword.lower() for keyword in config.get("required_keywords", [])]
        max_items = int(config.get("max_items", self.settings.max_source_items))

        collected: list[CollectedItem] = []
        for job in jobs:
            title = job.get("title", "").strip()
            absolute_url = job.get("absolute_url") or job.get("url")
            if not title or not absolute_url:
                continue

            location = (job.get("location") or {}).get("name") or ""
            departments = [entry.get("name", "") for entry in job.get("departments", []) if entry.get("name")]
            content_text = strip_html(job.get("content"))
            searchable_text = " ".join([title, location, " ".join(departments), content_text]).lower()

            if location_keywords and not any(keyword in searchable_text for keyword in location_keywords):
                continue
            if required_keywords and not any(keyword in searchable_text for keyword in required_keywords):
                continue

            tech_stack = split_keywords(searchable_text, required_keywords or location_keywords)
            posted_at = _parse_datetime(job.get("updated_at") or job.get("created_at"))
            role = departments[0] if departments else config.get("default_role")
            company_name = config.get("company_name") or source.name

            collected.append(
                CollectedItem(
                    source_type=source.source_type,
                    source_name=source.name,
                    title=title,
                    company_name=company_name,
                    url=absolute_url,
                    location=location or None,
                    role=role,
                    tech_stack=tech_stack,
                    raw_text=content_text,
                    posted_at=posted_at,
                    metadata={"departments": departments},
                )
            )
            if len(collected) >= max_items:
                break
        return collected


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
