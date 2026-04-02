from __future__ import annotations

from datetime import datetime, timezone

from core.schemas import CollectedItem
from database.models import Opportunity, Summary


class FakeCollector:
    def collect(self, source):
        item = CollectedItem(
            source_type="job",
            source_name=source.name,
            title="AI Cloud Engineer",
            company_name="테스트회사",
            url="https://example.com/jobs/1",
            location="Seoul, Korea",
            role="Platform Engineer",
            tech_stack=["ai", "cloud"],
            raw_text="Cloud AI platform engineer role",
            posted_at=datetime.now(timezone.utc),
        )
        return [item, item]


def test_collection_deduplicates_items(app, monkeypatch):
    monkeypatch.setattr("services.collection_service.build_collector", lambda kind, settings: FakeCollector())

    with app.state.db.session_scope() as session:
        stats = app.state.collection_service.collect_all(session)

    with app.state.db.session_scope() as session:
        opportunities = session.query(Opportunity).all()
        summaries = session.query(Summary).all()

    assert len(stats) == 1
    assert stats[0].new_items == 1
    assert stats[0].duplicate_items == 1
    assert len(opportunities) == 1
    assert len(summaries) == 1
