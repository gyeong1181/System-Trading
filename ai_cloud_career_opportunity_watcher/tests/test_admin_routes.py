from __future__ import annotations

from database.models import Opportunity
from tests.helpers import seed_opportunity


def test_admin_approve_flow(client):
    opportunity_id = seed_opportunity(client.app, title="승인 테스트", status="pending")

    response = client.post(
        f"/admin/opportunities/{opportunity_id}/approve",
        data={"note": "검토 완료"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    with client.app.state.db.session_scope() as session:
        opportunity = session.query(Opportunity).filter(Opportunity.id == opportunity_id).one()
        assert opportunity.status == "approved"
        assert opportunity.approval_queue.status == "approved"
        assert opportunity.approval_queue.note == "검토 완료"
