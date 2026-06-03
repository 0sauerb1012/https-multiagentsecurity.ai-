from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import httpx

from ..config import settings
from ..models import Paper


ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


@dataclass
class ArxivSearchResult:
    total_results: int
    papers: list[Paper]


class ArxivClient:
    async def search(
        self,
        query: str,
        *,
        start: int = 0,
        max_results: int | None = None,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> ArxivSearchResult:
        limit = max(1, min(max_results or settings.default_max_results, 200))
        params = {
            "search_query": query,
            "start": start,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(settings.arxiv_base_url, params=params)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError("Timed out while contacting arXiv.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"arXiv returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Network error while contacting arXiv: {exc!r}") from exc

        return self._parse_feed(response.text)

    def _parse_feed(self, xml_text: str) -> ArxivSearchResult:
        root = ET.fromstring(xml_text)
        total_results_text = root.findtext("opensearch:totalResults", default="0", namespaces=ATOM_NS)
        total_results = int(total_results_text)
        papers = [self._parse_entry(entry) for entry in root.findall("atom:entry", ATOM_NS)]
        return ArxivSearchResult(total_results=total_results, papers=papers)

    def _parse_entry(self, entry: ET.Element) -> Paper:
        links = entry.findall("atom:link", ATOM_NS)
        pdf_url = None
        paper_url = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        for link in links:
            href = link.attrib.get("href")
            title = link.attrib.get("title")
            rel = link.attrib.get("rel")
            if rel == "alternate" and href:
                paper_url = href
            if title == "pdf" and href:
                pdf_url = href

        authors = [
            author.findtext("atom:name", default="", namespaces=ATOM_NS).strip()
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        categories = [category.attrib.get("term", "") for category in entry.findall("atom:category", ATOM_NS)]
        primary_category = entry.find("arxiv:primary_category", ATOM_NS)

        return Paper(
            id=paper_url.rsplit("/", maxsplit=1)[-1],
            title=self._clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS)),
            summary=self._clean_text(entry.findtext("atom:summary", default="", namespaces=ATOM_NS)),
            published=entry.findtext("atom:published", default="", namespaces=ATOM_NS),
            updated=entry.findtext("atom:updated", default="", namespaces=ATOM_NS),
            authors=[author for author in authors if author],
            categories=[category for category in categories if category],
            primary_category=primary_category.attrib.get("term") if primary_category is not None else None,
            arxiv_id=paper_url.rsplit("/", maxsplit=1)[-1],
            venue="arXiv",
            source_name="arXiv",
            source_type="preprint",
            paper_url=paper_url,
            pdf_url=pdf_url,
        )

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(value.split())


def build_query(
    topic: str,
    *,
    categories: list[str] | None = None,
    include_terms: list[str] | None = None,
    exclude_terms: list[str] | None = None,
) -> str:
    terms = [f'all:"{topic}"']

    for category in categories or []:
        terms.append(f"cat:{category}")

    for term in include_terms or []:
        terms.append(f'all:"{term}"')

    for term in exclude_terms or []:
        terms.append(f'NOT all:"{term}"')

    return " AND ".join(terms)


def build_query_url(query: str, *, max_results: int, sort_by: str, sort_order: str) -> str:
    params: dict[str, Any] = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    return f"{settings.arxiv_base_url}?{urlencode(params)}"
