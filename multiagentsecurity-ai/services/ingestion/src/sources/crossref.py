from __future__ import annotations


def fetch(limit: int = 10) -> list[dict]:
    """Fetch placeholder records from Crossref.

    TODO: support query configuration, DOI enrichment, and backoff behavior.
    """

    return [
        {
            "source_name": "crossref",
            "source_identifier": "crossref-0001",
            "title": "Planner Executor Coordination Boundaries",
            "summary": "Placeholder Crossref article for taxonomy testing.",
            "url": "https://doi.org/10.0000/placeholder",
            "authors": ["Example Researcher"],
        }
    ][:limit]
