from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.schemas import CollectedItem


RELEVANCE_KEYWORDS = {
    "ai": 20,
    "machine learning": 20,
    "ml": 10,
    "llm": 16,
    "cloud": 16,
    "aws": 12,
    "gcp": 12,
    "azure": 12,
    "data": 10,
    "platform": 8,
    "infra": 10,
    "infrastructure": 10,
    "devops": 12,
    "kubernetes": 12,
    "backend": 6,
}

URGENCY_KEYWORDS = {
    "hiring now": 12,
    "urgent": 12,
    "closing soon": 16,
    "apply now": 10,
}


def score_item(item: CollectedItem) -> tuple[float, float]:
    searchable = " ".join(
        [
            item.title,
            item.company_name,
            item.location or "",
            item.role or "",
            " ".join(item.tech_stack),
            item.raw_text,
        ]
    ).lower()

    relevance = 0.0
    for keyword, weight in RELEVANCE_KEYWORDS.items():
        if keyword in searchable:
            relevance += weight

    if any(keyword in searchable for keyword in ["seoul", "korea", "south korea"]):
        relevance += 15

    if item.source_type == "job":
        relevance += 10

    urgency = 0.0
    for keyword, weight in URGENCY_KEYWORDS.items():
        if keyword in searchable:
            urgency += weight

    now = datetime.now(timezone.utc)
    if item.posted_at:
        posted_at = _ensure_aware(item.posted_at)
        age = now - posted_at
        if age <= timedelta(days=2):
            urgency += 25
        elif age <= timedelta(days=7):
            urgency += 15
        elif age <= timedelta(days=14):
            urgency += 5

    if item.expires_at:
        expires_at = _ensure_aware(item.expires_at)
        remaining = expires_at - now
        if remaining <= timedelta(days=3):
            urgency += 25
        elif remaining <= timedelta(days=7):
            urgency += 15

    return min(relevance, 100.0), min(urgency, 100.0)


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
