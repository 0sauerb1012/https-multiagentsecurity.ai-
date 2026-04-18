"""OpenAlex source integration for the local research hub."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from api.app.config import settings
from api.app.models import Paper


@dataclass(frozen=True)
class OpenAlexSearchResult:
    total_results: int
    papers: list[Paper]


class OpenAlexClient:
    async def search(
        self,
        query: str,
        *,
        per_page: int = 10,
    ) -> OpenAlexSearchResult:
        params = {
            "search": query,
            "per-page": max(1, min(per_page, settings.max_results_limit * 3)),
            "sort": "publication_date:desc",
        }
        if settings.openalex_email:
            params["mailto"] = settings.openalex_email

        headers: dict[str, str] = {}
        if settings.openalex_api_key:
            headers["Authorization"] = f"Bearer {settings.openalex_api_key}"

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.get(settings.openalex_base_url, params=params, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError("Timed out while contacting OpenAlex.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"OpenAlex returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Network error while contacting OpenAlex: {exc!r}") from exc

        payload = response.json()
        results = payload.get("results", [])
        meta = payload.get("meta", {})
        return OpenAlexSearchResult(
            total_results=int(meta.get("count", 0) or 0),
            papers=[self._parse_work(item) for item in results],
        )

    def _parse_work(self, work: dict) -> Paper:
        doi = (work.get("doi") or "").strip()
        ids = work.get("ids") or {}
        openalex_id = ids.get("openalex") or work.get("id") or ""
        primary_location = work.get("primary_location") or {}
        landing_page_url = primary_location.get("landing_page_url") or doi or openalex_id
        pdf_url = primary_location.get("pdf_url")
        source = primary_location.get("source") or {}
        host_venue = source.get("display_name") or "OpenAlex"

        return Paper(
            id=str(openalex_id or landing_page_url),
            title=(work.get("display_name") or "").strip(),
            summary=self._extract_abstract(work),
            published=str(work.get("publication_date") or ""),
            updated=str(work.get("updated_date") or work.get("publication_date") or ""),
            authors=self._extract_authors(work),
            categories=self._extract_topics(work),
            primary_category=(self._extract_topics(work) or [None])[0],
            doi=doi or None,
            arxiv_id=(external_ids.get("arxiv") if isinstance((external_ids := ids), dict) else None),
            venue=host_venue,
            source_name=f"OpenAlex · {host_venue}",
            source_type=self._resolve_source_type(work),
            paper_url=landing_page_url,
            pdf_url=pdf_url,
        )

    def _extract_authors(self, work: dict) -> list[str]:
        authorships = work.get("authorships") or []
        authors: list[str] = []
        for authorship in authorships:
            author = authorship.get("author") or {}
            name = (author.get("display_name") or "").strip()
            if name:
                authors.append(name)
        return authors

    def _extract_topics(self, work: dict) -> list[str]:
        topics = work.get("topics") or []
        names = []
        for topic in topics:
            name = (topic.get("display_name") or "").strip()
            if name:
                names.append(name)
        return names[:5]

    def _extract_abstract(self, work: dict) -> str:
        abstract_index = work.get("abstract_inverted_index") or {}
        if not abstract_index:
            return "Abstract unavailable from OpenAlex metadata."

        ordered_tokens = sorted(
            ((position, token) for token, positions in abstract_index.items() for position in positions),
            key=lambda item: item[0],
        )
        return " ".join(token for _, token in ordered_tokens).strip()

    def _resolve_source_type(self, work: dict) -> str:
        source_type = ((work.get("primary_location") or {}).get("source") or {}).get("type")
        if source_type:
            return str(source_type)
        work_type = work.get("type")
        return str(work_type or "scholarly work")
