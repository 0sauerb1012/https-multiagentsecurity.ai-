"""Crossref source integration for the local research hub."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from api.app.config import settings
from api.app.models import Paper


@dataclass(frozen=True)
class CrossrefSearchResult:
    total_results: int
    papers: list[Paper]


class CrossrefClient:
    async def search(
        self,
        query: str,
        *,
        rows: int = 10,
    ) -> CrossrefSearchResult:
        params = {
            "query": query,
            "rows": max(1, min(rows, settings.max_results_limit * 3)),
            "sort": "published",
            "order": "desc",
        }
        headers: dict[str, str] = {}
        if settings.crossref_email:
            headers["User-Agent"] = (
                f"multi-agent-security-research-hub/0.1 (mailto:{settings.crossref_email})"
            )

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.get(settings.crossref_base_url, params=params, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError("Timed out while contacting Crossref.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Crossref returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Network error while contacting Crossref: {exc!r}") from exc

        payload = response.json()
        message = payload.get("message") or {}
        items = message.get("items") or []
        return CrossrefSearchResult(
            total_results=int(message.get("total-results", 0) or 0),
            papers=[self._parse_item(item) for item in items],
        )

    def _parse_item(self, item: dict) -> Paper:
        doi = (item.get("DOI") or "").strip()
        paper_url = (item.get("URL") or "").strip() or (f"https://doi.org/{doi}" if doi else "")
        title_values = item.get("title") or []
        abstract = (item.get("abstract") or "").strip()
        container_title = (item.get("container-title") or ["Crossref"]).pop(0)
        subject = item.get("subject") or []

        return Paper(
            id=doi or paper_url or (title_values[0] if title_values else "crossref-record"),
            title=(title_values[0] if title_values else "Untitled work").strip(),
            summary=self._clean_abstract(abstract) or "Abstract unavailable from Crossref metadata.",
            published=self._extract_date(item, "published-print", "published-online", "issued"),
            updated=self._extract_date(item, "deposited", "indexed", "created"),
            authors=self._extract_authors(item),
            categories=[entry.strip() for entry in subject if str(entry).strip()],
            primary_category=(subject[0].strip() if subject else None),
            doi=doi or None,
            venue=container_title,
            source_name=f"Crossref · {container_title}",
            source_type=str(item.get("type") or "scholarly work"),
            paper_url=paper_url,
            pdf_url=self._extract_pdf_url(item),
        )

    def _extract_authors(self, item: dict) -> list[str]:
        authors = []
        for author in item.get("author") or []:
            given = (author.get("given") or "").strip()
            family = (author.get("family") or "").strip()
            full_name = " ".join(part for part in [given, family] if part).strip()
            if full_name:
                authors.append(full_name)
        return authors

    def _extract_pdf_url(self, item: dict) -> str | None:
        links = item.get("link") or []
        for link in links:
            if str(link.get("content-type") or "").lower() == "application/pdf":
                url = (link.get("URL") or "").strip()
                if url:
                    return url
        return None

    def _extract_date(self, item: dict, *keys: str) -> str:
        for key in keys:
            node = item.get(key) or {}
            parts = (node.get("date-parts") or [[]])[0]
            if parts:
                padded = [str(part) for part in parts[:3]]
                while len(padded) < 3:
                    padded.append("1")
                return "-".join(f"{int(part):02d}" if index else str(int(part)) for index, part in enumerate(padded))
        return ""

    def _clean_abstract(self, value: str) -> str:
        cleaned = value.replace("<jats:p>", " ").replace("</jats:p>", " ")
        cleaned = cleaned.replace("<jats:title>", " ").replace("</jats:title>", " ")
        return " ".join(cleaned.split())
