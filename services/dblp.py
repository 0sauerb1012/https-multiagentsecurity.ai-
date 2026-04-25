"""DBLP source integration for the local research hub."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from api.app.config import settings
from api.app.models import Paper


@dataclass(frozen=True)
class DblpSearchResult:
    total_results: int
    papers: list[Paper]


class DblpClient:
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> DblpSearchResult:
        params = {
            "q": query,
            "format": "json",
            "h": max(1, min(limit, 1000)),
            "f": max(0, offset),
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(settings.dblp_base_url, params=params)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError("Timed out while contacting DBLP.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"DBLP returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Network error while contacting DBLP: {exc!r}") from exc

        payload = response.json()
        result_block = (payload.get("result") or {}).get("hits") or {}
        total = int(result_block.get("@total", 0) or 0)
        hits = result_block.get("hit") or []
        if isinstance(hits, dict):
            hits = [hits]

        return DblpSearchResult(
            total_results=total,
            papers=[self._parse_hit(hit) for hit in hits],
        )

    def _parse_hit(self, hit: dict) -> Paper:
        info = hit.get("info") or {}
        title = (info.get("title") or "Untitled work").strip()
        venue = (info.get("venue") or "").strip() or None
        year = (info.get("year") or "").strip()
        authors_block = info.get("authors") or {}
        authors_data = authors_block.get("author") or []
        if isinstance(authors_data, str):
            authors = [authors_data]
        else:
            authors = [author.strip() for author in authors_data if str(author).strip()]
        doi = (info.get("doi") or "").strip() or None
        record_url = (info.get("url") or "").strip()
        paper_url = record_url or (f"https://doi.org/{doi}" if doi else "")

        return Paper(
            id=(info.get("key") or doi or paper_url or title),
            title=title,
            summary="Abstract unavailable from DBLP metadata.",
            published=f"{year}-01-01" if year else "",
            updated=f"{year}-01-01" if year else "",
            authors=authors,
            categories=[entry.strip() for entry in [venue] if entry],
            primary_category=venue,
            doi=doi,
            venue=venue,
            source_name=f"DBLP · {venue or 'Computer Science Bibliography'}",
            source_type="bibliographic index",
            paper_url=paper_url,
            pdf_url=None,
        )
