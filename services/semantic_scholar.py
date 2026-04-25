"""Semantic Scholar source integration for the local research hub."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from api.app.config import settings
from api.app.models import Paper


@dataclass(frozen=True)
class SemanticScholarSearchResult:
    total_results: int
    papers: list[Paper]


class SemanticScholarClient:
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        year_start: int | None = None,
    ) -> SemanticScholarSearchResult:
        params = {
            "query": f'"{query}"' if " " in query and '"' not in query else query,
            "fields": "title,url,abstract,authors,publicationDate,publicationTypes,openAccessPdf,venue,externalIds",
            "sort": "publicationDate:desc",
            "limit": max(1, min(limit, 100)),
            "offset": max(0, offset),
        }
        if year_start is not None:
            params["year"] = f"{year_start}-"
        headers: dict[str, str] = {}
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.get(settings.semantic_scholar_base_url, params=params, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError("Timed out while contacting Semantic Scholar.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Semantic Scholar returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Network error while contacting Semantic Scholar: {exc!r}") from exc

        payload = response.json()
        return SemanticScholarSearchResult(
            total_results=int(payload.get("total", 0) or 0),
            papers=[self._parse_item(item) for item in payload.get("data") or []],
        )

    def _parse_item(self, item: dict) -> Paper:
        open_access_pdf = item.get("openAccessPdf") or {}
        venue = (item.get("venue") or "").strip() or "Semantic Scholar"
        publication_types = item.get("publicationTypes") or []
        external_ids = item.get("externalIds") or {}
        paper_url = (item.get("url") or "").strip()
        doi = (external_ids.get("DOI") or "").strip()
        if not paper_url and doi:
            paper_url = f"https://doi.org/{doi}"

        return Paper(
            id=(item.get("paperId") or doi or paper_url or item.get("title") or "semantic-scholar-record"),
            title=(item.get("title") or "Untitled work").strip(),
            summary=(item.get("abstract") or "Abstract unavailable from Semantic Scholar metadata.").strip(),
            published=str(item.get("publicationDate") or ""),
            updated=str(item.get("publicationDate") or ""),
            authors=[author.get("name", "").strip() for author in item.get("authors") or [] if author.get("name")],
            categories=[entry.strip() for entry in publication_types if str(entry).strip()],
            primary_category=(publication_types[0].strip() if publication_types else None),
            doi=doi or None,
            venue=venue,
            source_name=f"Semantic Scholar · {venue}",
            source_type="scholarly work",
            paper_url=paper_url,
            pdf_url=(open_access_pdf.get("url") or "").strip() or None,
        )
