from __future__ import annotations

import hashlib

from core.schemas import CollectedItem
from core.text import collapse_whitespace


def build_dedupe_hash(item: CollectedItem) -> str:
    parts = [
        item.source_type,
        item.company_name.lower(),
        item.title.lower(),
        normalize_url(item.url),
        collapse_whitespace(item.location or "").lower(),
    ]
    digest_input = "||".join(parts)
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()
