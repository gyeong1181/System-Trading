from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.helpers import seed_opportunity


def test_digest_contains_weekly_section_and_action(app):
    now = datetime.now(timezone.utc)
    seed_opportunity(app, title="기회 1", status="approved", created_at=now - timedelta(days=1))
    seed_opportunity(app, title="기회 2", status="approved", created_at=now - timedelta(days=2))
    seed_opportunity(app, title="기회 3", status="approved", created_at=now - timedelta(days=3))

    with app.state.db.session_scope() as session:
        payload = app.state.digest_service.build_digest(session)

    assert "이번 주 주목할 만한 기회 3개" in payload.text
    assert "타깃 독자가 지금 할 행동 1개" in payload.text
    assert "기회 1" in payload.text
    assert payload.item_count == 3
