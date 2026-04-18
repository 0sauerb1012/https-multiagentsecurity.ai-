from __future__ import annotations


def fetch(limit: int = 10) -> list[dict]:
    """Fetch placeholder article records from arXiv.

    TODO: replace with real API integration, pagination, and source mapping.
    """

    return [
        {
            "source_name": "arxiv",
            "source_identifier": "arxiv-0001",
            "title": "Shared Memory Threats in Multi-Agent Systems",
            "summary": "Placeholder arXiv article for ingestion pipeline testing.",
            "url": "https://arxiv.org/abs/placeholder-0001",
            "authors": ["Example Author"],
        }
    ][:limit]
