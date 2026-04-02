from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from core.enums import ApprovalStatus, OpportunityStatus
from database.models import ApprovalQueue, Opportunity


class ApprovalService:
    def get_pending_items(self, session: Session) -> list[Opportunity]:
        return (
            session.query(Opportunity)
            .options(joinedload(Opportunity.summary), joinedload(Opportunity.approval_queue))
            .join(ApprovalQueue)
            .filter(ApprovalQueue.status == ApprovalStatus.PENDING.value)
            .order_by(Opportunity.relevance_score.desc(), Opportunity.urgency_score.desc(), Opportunity.created_at.desc())
            .all()
        )

    def get_reviewable_items(self, session: Session) -> list[Opportunity]:
        return (
            session.query(Opportunity)
            .options(joinedload(Opportunity.summary), joinedload(Opportunity.approval_queue))
            .join(ApprovalQueue)
            .order_by(
                ApprovalQueue.status.asc(),
                Opportunity.relevance_score.desc(),
                Opportunity.urgency_score.desc(),
                Opportunity.created_at.desc(),
            )
            .all()
        )

    def update_status(
        self,
        session: Session,
        opportunity_id: int,
        status: str,
        reviewed_by: str,
        note: str | None = None,
    ) -> Opportunity:
        opportunity = session.scalar(
            select(Opportunity)
            .options(joinedload(Opportunity.approval_queue), joinedload(Opportunity.summary))
            .where(Opportunity.id == opportunity_id)
        )
        if not opportunity or not opportunity.approval_queue:
            raise LookupError("검토 대상 항목을 찾을 수 없습니다.")

        opportunity.status = {
            ApprovalStatus.APPROVED.value: OpportunityStatus.APPROVED.value,
            ApprovalStatus.REJECTED.value: OpportunityStatus.REJECTED.value,
        }.get(status, OpportunityStatus.PENDING.value)
        opportunity.approval_queue.status = status
        opportunity.approval_queue.reviewed_by = reviewed_by
        opportunity.approval_queue.reviewed_at = datetime.now(timezone.utc)
        opportunity.approval_queue.note = note
        session.flush()
        return opportunity
