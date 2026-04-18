from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Article:
    source_name: str
    source_identifier: str
    title: str
    slug: str
    summary: str
    url: str
    published_at: datetime | None = None
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    raw_payload: dict = field(default_factory=dict)

    # TODO: expand with citations, DOI, PDF URL, and provenance fields as needed.
