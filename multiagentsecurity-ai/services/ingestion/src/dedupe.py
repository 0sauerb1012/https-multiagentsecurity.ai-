from __future__ import annotations

from models.article import Article


def dedupe_articles(articles: list[Article]) -> list[Article]:
    """Deduplicate by slug as a temporary stand-in for stronger identity logic."""

    deduped: dict[str, Article] = {}

    for article in articles:
        deduped[article.slug] = article

    # TODO: add DOI, URL canonicalization, and source precedence rules.
    return list(deduped.values())
