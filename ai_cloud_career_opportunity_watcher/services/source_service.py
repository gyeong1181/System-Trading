from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Source


class SourceService:
    def __init__(self, source_catalog_path: str) -> None:
        raw_path = Path(source_catalog_path)
        if raw_path.is_absolute():
            self.source_catalog_path = raw_path
        else:
            self.source_catalog_path = Path(__file__).resolve().parents[1] / raw_path

    def sync_catalog(self, session: Session) -> int:
        catalog = self.load_catalog()
        existing = {source.name: source for source in session.scalars(select(Source)).all()}
        created_or_updated = 0

        for entry in catalog:
            record = existing.get(entry["name"])
            if record is None:
                record = Source(
                    name=entry["name"],
                    source_type=entry["source_type"],
                    collector_kind=entry["collector_kind"],
                    url=entry["url"],
                    config_json=entry.get("config", {}),
                    is_active=entry.get("is_active", True),
                )
                session.add(record)
                created_or_updated += 1
                continue

            record.source_type = entry["source_type"]
            record.collector_kind = entry["collector_kind"]
            record.url = entry["url"]
            record.config_json = entry.get("config", {})
            record.is_active = entry.get("is_active", True)
            created_or_updated += 1
        return created_or_updated

    def load_catalog(self) -> list[dict]:
        if not self.source_catalog_path.exists():
            raise FileNotFoundError(f"소스 카탈로그를 찾을 수 없습니다: {self.source_catalog_path}")
        return json.loads(self.source_catalog_path.read_text(encoding="utf-8"))
