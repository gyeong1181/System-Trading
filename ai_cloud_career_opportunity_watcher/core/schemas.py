from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CollectedItem:
    source_type: str
    source_name: str
    title: str
    company_name: str
    url: str
    location: str | None = None
    role: str | None = None
    tech_stack: list[str] = field(default_factory=list)
    raw_text: str = ""
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
