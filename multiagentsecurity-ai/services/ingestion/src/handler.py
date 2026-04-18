from __future__ import annotations

from config import get_settings
from db import save_articles
from dedupe import dedupe_articles
from normalize import normalize_articles
from sources import arxiv, crossref, rss
from tagging import apply_tags


def lambda_handler(event: dict | None, context: object | None) -> dict:
    settings = get_settings()
    raw_items: list[dict] = []

    if settings.enable_arxiv:
        raw_items.extend(arxiv.fetch(limit=settings.article_limit))
    if settings.enable_crossref:
        raw_items.extend(crossref.fetch(limit=settings.article_limit))
    if settings.enable_rss:
        raw_items.extend(rss.fetch(limit=settings.article_limit))

    normalized = normalize_articles(raw_items)
    deduped = dedupe_articles(normalized)
    tagged = apply_tags(deduped)
    persistence = save_articles(settings, tagged)

    return {
        "environment": settings.environment,
        "received": len(raw_items),
        "normalized": len(normalized),
        "deduped": len(deduped),
        "saved": persistence["saved"],
        "skipped": persistence["skipped"],
    }


if __name__ == "__main__":
    print(lambda_handler(event={}, context=None))
