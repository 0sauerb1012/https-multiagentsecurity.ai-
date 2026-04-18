from __future__ import annotations

from models.article import Article


def apply_tags(articles: list[Article]) -> list[Article]:
    """Attach taxonomy hints with intentionally simple placeholder logic."""

    for article in articles:
        lowered = f"{article.title} {article.summary}".lower()

        if "prompt" in lowered and "prompt-injection" not in article.tags:
            article.tags.append("prompt-injection")
        if "memory" in lowered and "memory-poisoning" not in article.tags:
            article.tags.append("memory-poisoning")
        if "planner" in lowered and "planner-executor" not in article.tags:
            article.tags.append("planner-executor")

        if not article.categories:
            article.categories.append("research")

    # TODO: move to configurable taxonomy rules or model-assisted tagging.
    return articles
