from __future__ import annotations

from dataclasses import asdict

from config import Settings
from models.article import Article


def save_articles(settings: Settings, articles: list[Article]) -> dict[str, int]:
    """Persist normalized articles.

    TODO: replace this placeholder with a real PostgreSQL implementation using a
    lightweight client and idempotent upsert behavior.
    """

    if not settings.database_url:
        return {"saved": 0, "skipped": len(articles)}

    _ = [asdict(article) for article in articles]
    return {"saved": len(articles), "skipped": 0}
