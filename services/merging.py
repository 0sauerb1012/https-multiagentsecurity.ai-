"""Canonical merge pipeline for multi-source scholarly records."""

from __future__ import annotations

import re
from dataclasses import dataclass

from api.app.models import Paper, SourceRecord


@dataclass(frozen=True)
class MergeCluster:
    cluster_key: str
    records: list[Paper]


class PaperMergingService:
    """Deterministically cluster and merge source records into canonical papers.

    Extension points:
    - add LLM-assisted conflict resolution for ambiguous clusters
    - add stronger title similarity and author overlap scoring
    - attach field-level provenance/confidence
    """

    def cluster_and_merge(self, papers: list[Paper]) -> list[Paper]:
        clusters = self._cluster_records(papers)
        return [self._merge_cluster(cluster) for cluster in clusters]

    def _cluster_records(self, papers: list[Paper]) -> list[MergeCluster]:
        clusters: dict[str, list[Paper]] = {}
        title_index: dict[str, str] = {}

        for paper in papers:
            keys = self._candidate_keys(paper)
            cluster_key = None
            for key in keys:
                if key in clusters:
                    cluster_key = key
                    break
                if key.startswith("title:") and key in title_index:
                    cluster_key = title_index[key]
                    break

            if cluster_key is None:
                cluster_key = keys[0]
                clusters[cluster_key] = []

            clusters.setdefault(cluster_key, []).append(paper)
            for key in keys:
                if key.startswith("title:"):
                    title_index[key] = cluster_key
                else:
                    clusters.setdefault(key, clusters[cluster_key])

        deduped_clusters: dict[str, list[Paper]] = {}
        seen_lists: set[int] = set()
        for key, records in clusters.items():
            record_id = id(records)
            if record_id in seen_lists:
                continue
            seen_lists.add(record_id)
            deduped_clusters[key] = records

        return [MergeCluster(cluster_key=key, records=records) for key, records in deduped_clusters.items()]

    def _merge_cluster(self, cluster: MergeCluster) -> Paper:
        records = cluster.records
        best_title = self._prefer_text(records, "title")
        best_summary = self._prefer_summary(records)
        best_published = self._prefer_date(records, earliest=True)
        best_updated = self._prefer_date(records, earliest=False)
        best_pdf = self._prefer_pdf(records)
        best_url = self._prefer_url(records)
        best_primary = self._prefer_primary_category(records)
        best_venue = self._prefer_venue(records)
        best_source = self._prefer_source_label(records)
        merged_categories = self._merge_list_fields(records, "categories")
        merged_authors = self._merge_authors(records)
        merged_sources = self._merge_source_names(records)
        canonical_id = self._canonical_id(cluster.cluster_key, records)
        doi = self._first_non_empty(records, "doi")
        arxiv_id = self._first_non_empty(records, "arxiv_id")

        return Paper(
            id=canonical_id,
            canonical_id=canonical_id,
            title=best_title,
            summary=best_summary,
            published=best_published,
            updated=best_updated,
            authors=merged_authors,
            categories=merged_categories,
            primary_category=best_primary,
            doi=doi,
            arxiv_id=arxiv_id,
            venue=best_venue,
            source_name=best_source,
            source_type="merged scholarly record" if len(records) > 1 else records[0].source_type,
            merged_from_sources=merged_sources,
            source_records=[self._to_source_record(record) for record in records],
            paper_url=best_url,
            pdf_url=best_pdf,
            hub_categories=[],
        )

    def _candidate_keys(self, paper: Paper) -> list[str]:
        keys: list[str] = []
        if paper.doi:
            keys.append(f"doi:{self._normalize_url(paper.doi)}")
        if paper.arxiv_id:
            keys.append(f"arxiv:{paper.arxiv_id.lower()}")
        url_key = self._normalize_url(paper.paper_url)
        if url_key:
            keys.append(f"url:{url_key}")
        title_key = self._normalized_title_key(paper.title)
        if title_key:
            keys.append(title_key)
        return keys or [f"id:{paper.id.lower()}"]

    def _canonical_id(self, cluster_key: str, records: list[Paper]) -> str:
        doi = self._first_non_empty(records, "doi")
        if doi:
            return f"doi:{self._normalize_url(doi)}"
        arxiv_id = self._first_non_empty(records, "arxiv_id")
        if arxiv_id:
            return f"arxiv:{arxiv_id.lower()}"
        return cluster_key

    def _prefer_text(self, records: list[Paper], field: str) -> str:
        ranked = sorted(records, key=lambda paper: len(getattr(paper, field) or ""), reverse=True)
        return getattr(ranked[0], field) or ""

    def _prefer_summary(self, records: list[Paper]) -> str:
        meaningful = [
            record for record in records if getattr(record, "summary", "") and "unavailable" not in record.summary.lower()
        ]
        ranked = meaningful or records
        ranked = sorted(ranked, key=lambda paper: len(paper.summary or ""), reverse=True)
        return ranked[0].summary if ranked else ""

    def _prefer_date(self, records: list[Paper], *, earliest: bool) -> str:
        values = [record.published if earliest else record.updated for record in records]
        clean = sorted(value for value in values if value)
        if not clean:
            return ""
        return clean[0] if earliest else clean[-1]

    def _prefer_pdf(self, records: list[Paper]) -> str | None:
        for record in records:
            if record.source_name.startswith("arXiv") and record.pdf_url:
                return record.pdf_url
        for record in records:
            if record.pdf_url:
                return record.pdf_url
        return None

    def _prefer_url(self, records: list[Paper]) -> str:
        for record in records:
            if record.source_name.startswith("arXiv") and record.paper_url:
                return record.paper_url
        for record in records:
            if record.paper_url:
                return record.paper_url
        return ""

    def _prefer_primary_category(self, records: list[Paper]) -> str | None:
        for record in records:
            if record.primary_category:
                return record.primary_category
        return None

    def _prefer_venue(self, records: list[Paper]) -> str | None:
        for record in records:
            if record.venue:
                return record.venue
        return None

    def _prefer_source_label(self, records: list[Paper]) -> str:
        if len(records) == 1:
            return records[0].source_name
        return "Merged record"

    def _merge_list_fields(self, records: list[Paper], field: str) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for record in records:
            for entry in getattr(record, field):
                normalized = entry.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    values.append(normalized)
        return values[:8]

    def _merge_authors(self, records: list[Paper]) -> list[str]:
        return self._merge_list_fields(records, "authors")

    def _merge_source_names(self, records: list[Paper]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for record in records:
            base_name = record.source_name.split("·")[0].strip()
            if base_name not in seen:
                seen.add(base_name)
                names.append(base_name)
        return names

    def _to_source_record(self, record: Paper) -> SourceRecord:
        return SourceRecord(
            source_name=record.source_name,
            source_type=record.source_type,
            source_id=record.id,
            record_url=record.paper_url,
            title=record.title,
            summary=record.summary,
            authors=record.authors,
            published=record.published,
            doi=record.doi,
            arxiv_id=record.arxiv_id,
            venue=record.venue,
        )

    def _first_non_empty(self, records: list[Paper], field: str) -> str | None:
        for record in records:
            value = getattr(record, field)
            if value:
                return value
        return None

    def _normalized_title_key(self, title: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        return f"title:{normalized}" if normalized else ""

    def _normalize_url(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = lowered.replace("https://", "").replace("http://", "")
        lowered = lowered.replace("doi.org/", "")
        lowered = lowered.rstrip("/")
        return lowered
