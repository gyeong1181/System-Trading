from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from core.enums import DeliveryStatus, OpportunityStatus
from database.models import DeliveryLog, Opportunity
from integrations.telegram.client import TelegramClient


@dataclass(slots=True)
class DigestPayload:
    digest_date: date
    item_count: int
    text: str
    opportunity_ids: list[int]


class DigestService:
    def __init__(self, settings) -> None:
        self.settings = settings

    def build_digest(self, session: Session, digest_date: date | None = None) -> DigestPayload:
        digest_date = digest_date or datetime.now(timezone.utc).date()
        approved_or_sent_items = (
            session.query(Opportunity)
            .options(joinedload(Opportunity.summary), joinedload(Opportunity.approval_queue))
            .filter(Opportunity.status.in_([OpportunityStatus.APPROVED.value, OpportunityStatus.SENT.value]))
            .order_by(Opportunity.relevance_score.desc(), Opportunity.urgency_score.desc(), Opportunity.created_at.desc())
            .all()
        )
        unsent_items = [item for item in approved_or_sent_items if item.status == OpportunityStatus.APPROVED.value]
        now = datetime.now(timezone.utc)
        weekly_candidates = [
            item
            for item in approved_or_sent_items
            if _ensure_aware(item.created_at) >= now - timedelta(days=7)
        ][:3]

        if not unsent_items:
            text = (
                f"[{self.settings.app_name}] {digest_date.isoformat()} 일일 다이제스트\n\n"
                "오늘 승인된 항목이 없습니다.\n"
                "이번 주 주목할 만한 기회는 기존 승인 이력을 기준으로 다시 확인하세요."
            )
            return DigestPayload(digest_date=digest_date, item_count=0, text=text, opportunity_ids=[])

        lines = [
            f"[{self.settings.app_name}] {digest_date.isoformat()} 일일 다이제스트",
            "",
            "이번 주 주목할 만한 기회 3개",
        ]
        for index, item in enumerate(weekly_candidates, start=1):
            why_text = item.summary.why_it_matters if item.summary else "기업 변화와 채용 흐름을 함께 볼 수 있는 신호입니다."
            action_text = item.summary.recommended_action if item.summary else "관심 목록에 추가하고 공고 원문을 확인하세요."
            lines.extend(
                [
                    f"{index}. {item.title} | {item.company_name}",
                    f"왜 지금 봐야 하나: {why_text}",
                    f"당장 할 행동: {action_text}",
                ]
            )

        lines.extend(["", f"타깃 독자가 지금 할 행동 1개: {self._select_single_action(unsent_items)}", "", "오늘 승인된 항목"])

        for item in unsent_items:
            summary_text = item.summary.summary_text if item.summary else item.title
            why_text = item.summary.why_it_matters if item.summary else "원문 링크를 확인하세요."
            action_text = item.summary.recommended_action if item.summary else "검토 후 관심 목록에 추가하세요."
            lines.extend(
                [
                    f"- {item.title} | {item.company_name} | {item.source_type}",
                    summary_text,
                    f"왜 중요함: {why_text}",
                    f"추천 행동: {action_text}",
                    f"링크: {item.url}",
                    "",
                ]
            )

        text = "\n".join(lines).strip()
        return DigestPayload(
            digest_date=digest_date,
            item_count=len(unsent_items),
            text=text,
            opportunity_ids=[item.id for item in unsent_items],
        )

    def send_digest(self, session: Session, digest_date: date | None = None) -> DeliveryLog:
        payload = self.build_digest(session, digest_date=digest_date)
        client = TelegramClient(self.settings)
        try:
            response = client.send_message(payload.text)
            log = DeliveryLog(
                channel="telegram",
                digest_date=payload.digest_date,
                item_count=payload.item_count,
                status=DeliveryStatus.SUCCESS.value,
                response_text=str(response),
            )
            if payload.opportunity_ids:
                for opportunity in session.query(Opportunity).filter(Opportunity.id.in_(payload.opportunity_ids)).all():
                    opportunity.status = OpportunityStatus.SENT.value
            session.add(log)
            session.flush()
            return log
        except Exception as exc:
            log = DeliveryLog(
                channel="telegram",
                digest_date=payload.digest_date,
                item_count=payload.item_count,
                status=DeliveryStatus.FAILED.value,
                error_text=str(exc),
            )
            session.add(log)
            session.flush()
            raise

    def _select_single_action(self, items: list[Opportunity]) -> str:
        top_item = max(items, key=lambda item: item.relevance_score + item.urgency_score)
        if top_item.summary:
            return top_item.summary.recommended_action
        return "가장 점수가 높은 항목의 원문을 열고 24시간 안에 후속 메모를 남기세요."


def _ensure_aware(value):
    if value is None:
        return datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
