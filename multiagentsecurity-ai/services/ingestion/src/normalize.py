from __future__ import annotations

from models.article import Article


def normalize_articles(raw_items: list[dict]) -> list[Article]:
    """Convert heterogeneous source payloads into the common article shape."""

    articles: list[Article] = []

    for item in raw_items:
        title = item.get("title", "untitled record")
        slug = (
            item.get("slug")
            or title.lower().replace("/", "-").replace(" ", "-")
        )
        articles.append(
            Article(
                source_name=item.get("source_name", "unknown"),
                source_identifier=item.get("source_identifier", slug),
                title=title,
                slug=slug,
                summary=item.get("summary", "TODO: add normalized summary."),
                url=item.get("url", "https://example.com"),
                authors=item.get("authors", []),
                raw_payload=item,
            )
        )

    return articles
