from __future__ import annotations


def fetch(limit: int = 10) -> list[dict]:
    """Fetch placeholder records from RSS feeds.

    TODO: add configurable feed registry and content extraction.
    """

    return [
        {
            "source_name": "rss",
            "source_identifier": "rss-0001",
            "title": "Prompt Injection Notes from Industry Feed",
            "summary": "Placeholder RSS record describing a prompt injection finding.",
            "url": "https://example.com/rss-placeholder",
            "authors": ["Feed Author"],
        }
    ][:limit]
