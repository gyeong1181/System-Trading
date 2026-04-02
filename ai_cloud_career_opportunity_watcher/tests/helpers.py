from __future__ import annotations

from datetime import datetime, timezone

from database.models import ApprovalQueue, Company, Opportunity, Source, Summary


def seed_opportunity(
    app,
    *,
    title: str,
    company_name: str = "테스트회사",
    status: str = "pending",
    created_at: datetime | None = None,
):
    created_at = created_at or datetime.now(timezone.utc)
    with app.state.db.session_scope() as session:
        source = session.query(Source).first()
        company = session.query(Company).filter(Company.name == company_name).first()
        if company is None:
            company = Company(name=company_name, slug=company_name.lower())
            session.add(company)
            session.flush()

        opportunity = Opportunity(
            source=source,
            company=company,
            source_type="job",
            source_name=source.name,
            title=title,
            company_name=company_name,
            url=f"https://example.com/{title.replace(' ', '-').lower()}",
            location="Seoul, Korea",
            role="ML Engineer",
            tech_stack=["ai", "cloud"],
            raw_text="AI Cloud role for testing",
            relevance_score=82,
            urgency_score=64,
            dedupe_hash=f"hash-{title}",
            status=status,
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(opportunity)
        session.flush()
        session.add(
            Summary(
                opportunity=opportunity,
                title=title,
                company=company_name,
                category="job",
                summary_text=f"1) {title}\n2) Seoul, Korea\n3) 테스트 요약",
                why_it_matters="왜 지금 봐야 하는지 테스트 문구",
                recommended_action="당장 할 행동 테스트 문구",
                source_link=opportunity.url,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        session.add(
            ApprovalQueue(
                opportunity=opportunity,
                status="approved" if status in {"approved", "sent"} else "pending",
                created_at=created_at,
                updated_at=created_at,
            )
        )
        session.flush()
        return opportunity.id
