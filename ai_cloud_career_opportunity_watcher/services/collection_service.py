from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from collectors.registry import build_collector
from core.dedupe import build_dedupe_hash
from core.enums import ApprovalStatus, OpportunityStatus
from core.logger import get_logger
from core.schemas import CollectedItem
from database.models import ApprovalQueue, CollectionLog, Company, Opportunity, Source, Summary
from scorers.rule_based import score_item
from summarizers.heuristic import HeuristicSummarizer


@dataclass(slots=True)
class CollectionStats:
    source_name: str
    items_found: int = 0
    new_items: int = 0
    duplicate_items: int = 0
    message: str | None = None
    status: str = "success"


class CollectionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(self.__class__.__name__)
        self.summarizer = HeuristicSummarizer()

    def collect_all(self, session: Session) -> list[CollectionStats]:
        stats_list: list[CollectionStats] = []
        sources = session.scalars(select(Source).where(Source.is_active.is_(True)).order_by(Source.name)).all()
        for source in sources:
            stats_list.append(self.collect_source(session, source))
        return stats_list

    def collect_source(self, session: Session, source: Source) -> CollectionStats:
        collector = build_collector(source.collector_kind, self.settings)
        stats = CollectionStats(source_name=source.name)
        try:
            items = collector.collect(source)
            stats.items_found = len(items)
            for item in items:
                result = self._ingest_item(session, source, item)
                if result == "new":
                    stats.new_items += 1
                else:
                    stats.duplicate_items += 1
            source.last_collected_at = datetime.now(timezone.utc)
            source.last_message = f"{stats.new_items}개 신규, {stats.duplicate_items}개 중복"
        except Exception as exc:
            stats.status = "failed"
            stats.message = str(exc)
            source.last_message = str(exc)
            self.logger.exception("수집 실패: %s", source.name)
        finally:
            session.add(
                CollectionLog(
                    source_name=source.name,
                    status=stats.status,
                    items_found=stats.items_found,
                    new_items=stats.new_items,
                    duplicate_items=stats.duplicate_items,
                    message=stats.message,
                )
            )
            session.flush()
        return stats

    def _ingest_item(self, session: Session, source: Source, item: CollectedItem) -> str:
        dedupe_hash = build_dedupe_hash(item)
        existing = session.scalar(select(Opportunity).where(Opportunity.dedupe_hash == dedupe_hash))
        if existing:
            return "duplicate"

        relevance_score, urgency_score = score_item(item)
        company = self._get_or_create_company(session, item)
        opportunity = Opportunity(
            source=source,
            company=company,
            source_type=item.source_type,
            source_name=item.source_name,
            title=item.title,
            company_name=item.company_name,
            url=item.url,
            location=item.location,
            role=item.role,
            tech_stack=item.tech_stack,
            raw_text=item.raw_text,
            posted_at=item.posted_at,
            expires_at=item.expires_at,
            relevance_score=relevance_score,
            urgency_score=urgency_score,
            dedupe_hash=dedupe_hash,
            status=OpportunityStatus.PENDING.value,
        )
        session.add(opportunity)
        session.flush()

        summary_payload = self.summarizer.summarize(opportunity)
        session.add(
            Summary(
                opportunity=opportunity,
                title=summary_payload["title"],
                company=summary_payload["company"],
                category=summary_payload["category"],
                summary_text=summary_payload["summary_text"],
                why_it_matters=summary_payload["why_it_matters"],
                recommended_action=summary_payload["recommended_action"],
                source_link=summary_payload["source_link"],
            )
        )
        session.add(ApprovalQueue(opportunity=opportunity, status=ApprovalStatus.PENDING.value))

        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            return "duplicate"
        return "new"

    def _get_or_create_company(self, session: Session, item: CollectedItem) -> Company:
        company_name = item.company_name.strip()
        company = session.scalar(select(Company).where(Company.name == company_name))
        if company:
            return company

        slug = company_name.lower().replace("&", "and").replace("/", "-").replace(" ", "-")
        company = Company(name=company_name, slug=slug)
        session.add(company)
        session.flush()
        return company
