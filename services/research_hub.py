"""Coordinator for arXiv retrieval and summary generation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import math
from math import ceil

from api.app.models import Paper, RankedPaper, ReviewedPaper
from api.app.services.arxiv import ArxivClient
from api.app.services.openai_agents import OpenAIAgentService
from api.app.services.ranking import rank_papers

from .categorization import HUB_CATEGORY_LABELS, PaperCategorizationService
from .crossref import CrossrefClient
from .database import DatabaseService
from .date_utils import clamp_future_year
from .dblp import DblpClient
from .hub_types import (
    HeatmapRow,
    LandscapeEdge,
    LandscapeNode,
    LibraryCategoryGroup,
    PaperCard,
    ResearchHubResult,
)
from .merging import PaperMergingService
from .openalex import OpenAlexClient
from .semantic_scholar import SemanticScholarClient
from .summarization import PaperSummaryService
from .topic_catalog import (
    BROAD_AGENTIC_AI_TOPICS,
    FALLBACK_QUERY,
    MULTI_AGENT_SECURITY_FIELD_TOPIC,
    TopicDefinition,
)

class ResearchHubService:
    """Local-only service orchestration.

    Extension points:
    - add more academic APIs in `_load_topic_papers`
    - add relevance ranking before truncation in `fetch_latest_papers`
    - add research-gap detection after summarization
    - add visualization-specific aggregates without changing the route layer
    """

    def __init__(self) -> None:
        self.arxiv_client = ArxivClient()
        self.crossref_client = CrossrefClient()
        self.dblp_client = DblpClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_scholar_client = SemanticScholarClient()
        self.agent_service = OpenAIAgentService()
        self.categorization_service = PaperCategorizationService()
        self.merging_service = PaperMergingService()
        self.summary_service = PaperSummaryService()
        self.database_service = DatabaseService()
        self._source_page_sizes = {
            "arxiv": 200,
            "crossref": 200,
            "dblp": 200,
            "openalex": 200,
            "semantic_scholar": 100,
        }
        self._source_labels = {
            "arxiv": "arXiv",
            "crossref": "Crossref",
            "dblp": "DBLP",
            "openalex": "OpenAlex",
            "semantic_scholar": "Semantic Scholar",
        }

    async def fetch_latest_papers(
        self,
        *,
        limit: int = 12,
    ) -> ResearchHubResult:
        stored_snapshot = self._build_stored_snapshot(limit=limit)
        if stored_snapshot is not None:
            return stored_snapshot
        return await self._build_snapshot(limit=limit)

    def fetch_stored_latest_papers(self, *, limit: int = 12) -> ResearchHubResult:
        stored_snapshot = self._build_stored_snapshot(limit=limit)
        if stored_snapshot is None:
            raise ValueError("No stored papers are available yet. Run ingestion to populate the local database.")
        return stored_snapshot

    def fetch_stored_latest_papers_by_source(self, *, source_filter: str, limit: int = 12) -> ResearchHubResult:
        if not self.database_service.has_persisted_papers():
            raise ValueError("No stored papers are available yet. Run ingestion to populate the local database.")
        cards = self.database_service.load_cards_by_source(source_filter=source_filter, limit=limit)
        heatmap_rows, gap_labels, concentration_labels = self._build_heatmap(cards)
        landscape_nodes, landscape_edges = self._build_landscape(cards, heatmap_rows)
        return ResearchHubResult(
            cards=cards,
            feed_label=f'Stored multi-agent security corpus · {source_filter}',
            tracked_topics=[topic.label for topic in BROAD_AGENTIC_AI_TOPICS],
            heatmap_rows=heatmap_rows,
            landscape_nodes=landscape_nodes,
            landscape_edges=landscape_edges,
            gap_labels=gap_labels,
            concentration_labels=concentration_labels,
        )

    def fetch_stored_sources(self) -> list[str]:
        return self.database_service.load_available_sources()

    async def fetch_library_groups(self, *, limit: int = 24) -> list[LibraryCategoryGroup]:
        if self.database_service.has_persisted_papers():
            return self.database_service.load_library_groups()
        snapshot = await self._build_snapshot(limit=limit)
        groups: list[LibraryCategoryGroup] = []
        for label in HUB_CATEGORY_LABELS:
            matching_cards = [card for card in snapshot.cards if label in card.paper.hub_categories]
            if not matching_cards:
                continue
            groups.append(
                LibraryCategoryGroup(
                    slug=self.slugify_category(label),
                    category=label,
                    count=len(matching_cards),
                    cards=matching_cards[:3],
                )
            )
        groups.sort(key=lambda group: (-group.count, group.category))
        return groups

    async def fetch_area_papers(
        self,
        *,
        area_slug: str,
        limit: int | None = 36,
    ) -> tuple[str, list[PaperCard]]:
        if self.database_service.has_persisted_papers():
            return self.database_service.load_area_cards(area_slug=area_slug, limit=limit)
        snapshot = await self._build_snapshot(limit=limit)
        for row in snapshot.heatmap_rows:
            if row.slug == area_slug:
                cards = [card for card in snapshot.cards if row.category in card.paper.hub_categories]
                return row.category, cards
        raise ValueError("Unknown research area.")

    async def fetch_gap_snapshot(self) -> ResearchHubResult:
        if self.database_service.has_persisted_papers():
            cards = self.database_service.load_cards(limit=12)
            heatmap_rows, gap_labels, concentration_labels = self.database_service.load_heatmap_rows()
            landscape_nodes, landscape_edges = self._build_landscape(cards, heatmap_rows)
            return ResearchHubResult(
                cards=cards,
                feed_label="Stored multi-agent security corpus",
                tracked_topics=[topic.label for topic in BROAD_AGENTIC_AI_TOPICS],
                heatmap_rows=heatmap_rows,
                landscape_nodes=landscape_nodes,
                landscape_edges=landscape_edges,
                gap_labels=gap_labels,
                concentration_labels=concentration_labels,
            )
        return await self._build_snapshot(limit=12)

    async def fetch_paper_card(self, *, canonical_id: str) -> PaperCard:
        if self.database_service.has_persisted_papers():
            stored = self.database_service.load_card_by_canonical_id(canonical_id)
            if stored is not None:
                return stored

        snapshot = await self._build_snapshot(limit=60)
        for card in snapshot.cards:
            if (card.paper.canonical_id or card.paper.id) == canonical_id:
                return card
        raise ValueError("Unknown paper.")

    async def ingest_and_store(
        self,
        *,
        mode: str = "seed",
        target_limit: int = 1000,
        per_topic_limit: int = 60,
        years_back: int = 5,
        overlap_days: int = 3,
        reconcile_lookback_days: int = 30,
    ) -> dict[str, int | str]:
        target_limit = max(50, target_limit)
        per_topic_limit = max(10, per_topic_limit)
        years_back = max(1, years_back)
        overlap_days = max(1, overlap_days)
        reconcile_lookback_days = max(7, reconcile_lookback_days)
        topic_definitions = list(BROAD_AGENTIC_AI_TOPICS)
        run = self.database_service.start_run(
            mode=mode,
            notes=(
                f"{mode} ingestion target={target_limit}, per_topic_limit={per_topic_limit}, "
                f"years_back={years_back}, overlap_days={overlap_days}, "
                f"reconcile_lookback_days={reconcile_lookback_days}"
            )
        )
        fetched_count = 0
        merged_count = 0
        relevant_count = 0

        try:
            source_paper_sets = await asyncio.gather(
                *(
                    self._load_topic_papers(
                        topic,
                        mode=mode,
                        per_topic_limit=per_topic_limit,
                        years_back=years_back,
                        overlap_days=overlap_days,
                        reconcile_lookback_days=reconcile_lookback_days,
                    )
                    for topic in topic_definitions
                )
            )
            fetched_papers = [paper for papers in source_paper_sets for paper in papers]
            fetched_count = len(fetched_papers)
            merged_candidates = self.merging_service.cluster_and_merge(
                fetched_papers
            )
            merged_count = len(merged_candidates)
            candidates_for_review = merged_candidates
            if mode != "seed":
                existing_ids = self.database_service.known_canonical_ids(
                    [(paper.canonical_id or paper.id) for paper in merged_candidates]
                )
                candidates_for_review = [
                    paper for paper in merged_candidates if (paper.canonical_id or paper.id) not in existing_ids
                ]

            filtered_papers = await self._filter_for_multi_agent_security(candidates_for_review, limit=target_limit)
            filtered_papers.sort(
                key=lambda paper: (paper.fit_score, self._parse_datetime(paper.published)),
                reverse=True,
            )
            selected = filtered_papers[:target_limit]
            cards = await self._run_limited(selected, self._build_card, concurrency=4)
            relevant_count = len(cards)
            self.database_service.save_cards(cards, run_id=run.run_id, ingestion_mode=mode)
            self._update_source_sync_state(mode=mode, fetched_papers=fetched_papers)
            self.database_service.finish_run(
                run.run_id,
                status="completed",
                fetched_count=fetched_count,
                merged_count=merged_count,
                relevant_count=relevant_count,
                notes="Batch ingestion completed successfully.",
            )
            return {
                "run_id": run.run_id,
                "mode": mode,
                "fetched_count": fetched_count,
                "merged_count": merged_count,
                "relevant_count": relevant_count,
                "stored_count": len(cards),
                "database_path": str(self.database_service.db_path),
            }
        except Exception as exc:
            self.database_service.finish_run(
                run.run_id,
                status="failed",
                fetched_count=fetched_count,
                merged_count=merged_count,
                relevant_count=relevant_count,
                notes=str(exc).strip() or exc.__class__.__name__,
            )
            raise

    async def _build_snapshot(self, *, limit: int) -> ResearchHubResult:
        limit = max(1, min(limit, 60))
        years_back = 5
        cutoff = self._cutoff_datetime(years_back)
        topic_definitions = list(BROAD_AGENTIC_AI_TOPICS)
        per_topic_limit = max(8, ceil((limit * 3) / max(1, len(topic_definitions))) + 2)
        source_paper_sets = await asyncio.gather(
            *(
                self._load_topic_papers(
                    topic,
                    per_topic_limit=per_topic_limit,
                    years_back=years_back,
                )
                for topic in topic_definitions
            )
        )

        merged_candidates = self.merging_service.cluster_and_merge([paper for papers in source_paper_sets for paper in papers])

        if not merged_candidates:
            fallback_result = await self.arxiv_client.search(
                FALLBACK_QUERY,
                max_results=limit,
                sort_by="submittedDate",
                sort_order="descending",
            )
            merged_candidates = self.merging_service.cluster_and_merge(
                self._filter_recent_papers(fallback_result.papers, cutoff=cutoff)
            )

        filtered_papers = await self._filter_for_multi_agent_security(merged_candidates, limit=limit)
        newest_first = sorted(filtered_papers, key=lambda paper: self._parse_datetime(paper.published), reverse=True)[:limit]

        cards = await self._run_limited(newest_first, self._build_card, concurrency=4)
        heatmap_rows, gap_labels, concentration_labels = self._build_heatmap(cards)
        landscape_nodes, landscape_edges = self._build_landscape(cards, heatmap_rows)
        return ResearchHubResult(
            cards=cards,
            feed_label="Daily multi-agent security feed",
            tracked_topics=[topic.label for topic in topic_definitions],
            heatmap_rows=heatmap_rows,
            landscape_nodes=landscape_nodes,
            landscape_edges=landscape_edges,
            gap_labels=gap_labels,
            concentration_labels=concentration_labels,
        )

    async def _load_topic_papers(
        self,
        topic: TopicDefinition,
        *,
        mode: str,
        per_topic_limit: int,
        years_back: int,
        overlap_days: int,
        reconcile_lookback_days: int,
    ) -> list[Paper]:
        arxiv_cutoff = self._ingestion_cutoff(
            source_key="arxiv",
            mode=mode,
            years_back=years_back,
            overlap_days=overlap_days,
            reconcile_lookback_days=reconcile_lookback_days,
        )
        crossref_cutoff = self._ingestion_cutoff(
            source_key="crossref",
            mode=mode,
            years_back=years_back,
            overlap_days=overlap_days,
            reconcile_lookback_days=reconcile_lookback_days,
        )
        dblp_cutoff = self._ingestion_cutoff(
            source_key="dblp",
            mode=mode,
            years_back=years_back,
            overlap_days=overlap_days,
            reconcile_lookback_days=reconcile_lookback_days,
        )
        openalex_cutoff = self._ingestion_cutoff(
            source_key="openalex",
            mode=mode,
            years_back=years_back,
            overlap_days=overlap_days,
            reconcile_lookback_days=reconcile_lookback_days,
        )
        semantic_cutoff = self._ingestion_cutoff(
            source_key="semantic_scholar",
            mode=mode,
            years_back=years_back,
            overlap_days=overlap_days,
            reconcile_lookback_days=reconcile_lookback_days,
        )

        arxiv_task = self._fetch_arxiv_topic(topic.query, per_topic_limit=per_topic_limit, cutoff=arxiv_cutoff)
        crossref_task = self._fetch_crossref_topic(
            topic.query,
            per_topic_limit=per_topic_limit,
            cutoff=crossref_cutoff,
            cutoff_date=crossref_cutoff.date().isoformat(),
        )
        dblp_task = self._fetch_dblp_topic(topic.query, per_topic_limit=per_topic_limit, cutoff=dblp_cutoff)
        openalex_task = self._fetch_openalex_topic(
            topic.query,
            per_topic_limit=per_topic_limit,
            cutoff=openalex_cutoff,
            cutoff_date=openalex_cutoff.date().isoformat(),
        )
        semantic_scholar_task = self._fetch_semantic_scholar_topic(
            topic.query,
            per_topic_limit=per_topic_limit,
            cutoff=semantic_cutoff,
            year_start=semantic_cutoff.year,
        )
        results = await asyncio.gather(
            arxiv_task,
            crossref_task,
            dblp_task,
            openalex_task,
            semantic_scholar_task,
            return_exceptions=True,
        )

        papers: list[Paper] = []
        for result in results:
            if not isinstance(result, Exception):
                papers.extend(result)
        return papers

    def _update_source_sync_state(self, *, mode: str, fetched_papers: list[Paper]) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        for source_label in self._source_labels.values():
            matching = [
                paper for paper in fetched_papers if paper.source_name.split("·")[0].strip() == source_label
            ]
            watermark_published = None
            watermark_source_id = None
            if matching:
                newest = max(matching, key=lambda paper: self._parse_datetime(paper.published))
                watermark_published = clamp_future_year(newest.published)
                watermark_source_id = newest.doi or newest.arxiv_id or newest.id
            self.database_service.write_source_sync_state(
                source_name=source_label,
                last_successful_run_at=completed_at,
                high_watermark_published_at=watermark_published,
                high_watermark_source_id=watermark_source_id,
                notes=f"{mode} run completed",
            )

    async def _fetch_arxiv_topic(self, query: str, *, per_topic_limit: int, cutoff: datetime) -> list[Paper]:
        papers: list[Paper] = []
        start = 0
        page_size = self._source_page_sizes["arxiv"]
        while len(papers) < per_topic_limit:
            batch_size = min(page_size, per_topic_limit - len(papers))
            result = await self.arxiv_client.search(
                query,
                start=start,
                max_results=batch_size,
                sort_by="submittedDate",
                sort_order="descending",
            )
            if not result.papers:
                break
            fresh_batch = self._filter_recent_papers(result.papers, cutoff=cutoff)
            papers.extend(fresh_batch)
            start += len(result.papers)
            if len(result.papers) < batch_size or start >= result.total_results or self._batch_is_before_cutoff(result.papers, cutoff):
                break
        return papers[:per_topic_limit]

    async def _fetch_crossref_topic(
        self,
        query: str,
        *,
        per_topic_limit: int,
        cutoff: datetime,
        cutoff_date: str,
    ) -> list[Paper]:
        papers: list[Paper] = []
        offset = 0
        page_size = self._source_page_sizes["crossref"]
        while len(papers) < per_topic_limit:
            batch_size = min(page_size, per_topic_limit - len(papers))
            result = await self.crossref_client.search(
                query,
                rows=batch_size,
                offset=offset,
                from_pub_date=cutoff_date,
            )
            if not result.papers:
                break
            papers.extend(self._filter_recent_papers(result.papers, cutoff=cutoff))
            offset += len(result.papers)
            if len(result.papers) < batch_size or offset >= result.total_results or self._batch_is_before_cutoff(result.papers, cutoff):
                break
        return papers[:per_topic_limit]

    async def _fetch_dblp_topic(self, query: str, *, per_topic_limit: int, cutoff: datetime) -> list[Paper]:
        papers: list[Paper] = []
        offset = 0
        page_size = self._source_page_sizes["dblp"]
        while len(papers) < per_topic_limit:
            batch_size = min(page_size, per_topic_limit - len(papers))
            result = await self.dblp_client.search(query, limit=batch_size, offset=offset)
            if not result.papers:
                break
            papers.extend(self._filter_recent_papers(result.papers, cutoff=cutoff))
            offset += len(result.papers)
            if len(result.papers) < batch_size or offset >= result.total_results or self._batch_is_before_cutoff(result.papers, cutoff):
                break
        return papers[:per_topic_limit]

    async def _fetch_openalex_topic(
        self,
        query: str,
        *,
        per_topic_limit: int,
        cutoff: datetime,
        cutoff_date: str,
    ) -> list[Paper]:
        papers: list[Paper] = []
        page = 1
        page_size = self._source_page_sizes["openalex"]
        while len(papers) < per_topic_limit:
            batch_size = min(page_size, per_topic_limit - len(papers))
            result = await self.openalex_client.search(
                query,
                per_page=batch_size,
                page=page,
                from_publication_date=cutoff_date,
            )
            if not result.papers:
                break
            papers.extend(self._filter_recent_papers(result.papers, cutoff=cutoff))
            page += 1
            if len(result.papers) < batch_size or ((page - 1) * batch_size) >= result.total_results or self._batch_is_before_cutoff(result.papers, cutoff):
                break
        return papers[:per_topic_limit]

    async def _fetch_semantic_scholar_topic(
        self,
        query: str,
        *,
        per_topic_limit: int,
        cutoff: datetime,
        year_start: int,
    ) -> list[Paper]:
        papers: list[Paper] = []
        offset = 0
        page_size = self._source_page_sizes["semantic_scholar"]
        while len(papers) < per_topic_limit:
            batch_size = min(page_size, per_topic_limit - len(papers))
            result = await self.semantic_scholar_client.search(
                query,
                limit=batch_size,
                offset=offset,
                year_start=year_start,
            )
            if not result.papers:
                break
            papers.extend(self._filter_recent_papers(result.papers, cutoff=cutoff))
            offset += len(result.papers)
            if len(result.papers) < batch_size or offset >= result.total_results or self._batch_is_before_cutoff(result.papers, cutoff):
                break
        return papers[:per_topic_limit]

    async def _filter_for_multi_agent_security(self, papers: list[Paper], *, limit: int) -> list[ReviewedPaper]:
        if not papers:
            return []
        if not self.agent_service.is_enabled():
            raise RuntimeError("OpenAI review is required for this pipeline. Configure a working OPENAI_API_KEY.")
        if not self.agent_service.classifier_enabled():
            raise RuntimeError("OpenAI classification is required for this pipeline. Configure a working OPENAI_API_KEY.")

        ranked = rank_papers(MULTI_AGENT_SECURITY_FIELD_TOPIC, papers)
        review_pool = ranked[: max(limit * 3, 18)]
        reviewed = await self._run_limited(review_pool, self._review_candidate, concurrency=6)

        accepted = [paper for paper in reviewed if paper.is_fit]
        classified = await self._run_limited(accepted, self._classify_reviewed_paper, concurrency=6)
        accepted = [paper for paper in classified if paper.is_fit and paper.hub_categories]
        accepted.sort(key=lambda paper: (paper.fit_score, self._parse_datetime(paper.published)), reverse=True)
        return accepted

    async def _review_candidate(self, paper: RankedPaper) -> ReviewedPaper:
        decision = await self.agent_service.review_paper(
            topic=MULTI_AGENT_SECURITY_FIELD_TOPIC,
            min_fit_score=5.5,
            paper=paper,
            lexical_score=paper.relevance_score,
            lexical_rationale=paper.rationale,
        )
        return ReviewedPaper(
            **paper.model_dump(),
            is_fit=decision.is_fit and decision.fit_score >= 5.5,
            fit_score=decision.fit_score,
            reviewer_notes=decision.reviewer_notes,
        )

    async def _build_card(self, paper: ReviewedPaper) -> PaperCard:
        bullets = await self.summary_service.summarize(paper)
        return PaperCard(paper=paper, bullets=bullets)

    async def _classify_reviewed_paper(self, paper: ReviewedPaper) -> ReviewedPaper:
        heuristic = self.categorization_service.classify(paper)
        decision = await self.agent_service.classify_paper(
            topic=MULTI_AGENT_SECURITY_FIELD_TOPIC,
            taxonomy=list(HUB_CATEGORY_LABELS),
            paper=paper,
            reviewer_notes=paper.reviewer_notes,
            fallback_categories=heuristic.categories,
        )
        categories = decision.categories
        is_relevant = paper.is_fit and decision.is_relevant and bool(categories)
        confidence = decision.confidence
        rationale = decision.rationale

        return paper.model_copy(
            update={
                "hub_categories": categories,
                "is_fit": is_relevant and bool(categories),
                "classification_confidence": confidence,
                "classification_notes": rationale,
            }
        )

    def _build_stored_snapshot(self, *, limit: int) -> ResearchHubResult | None:
        if not self.database_service.has_persisted_papers():
            return None
        cards = self.database_service.load_cards(limit=limit)
        heatmap_rows, gap_labels, concentration_labels = self._build_heatmap(cards)
        landscape_nodes, landscape_edges = self._build_landscape(cards, heatmap_rows)
        return ResearchHubResult(
            cards=cards,
            feed_label="Stored multi-agent security corpus",
            tracked_topics=[topic.label for topic in BROAD_AGENTIC_AI_TOPICS],
            heatmap_rows=heatmap_rows,
            landscape_nodes=landscape_nodes,
            landscape_edges=landscape_edges,
            gap_labels=gap_labels,
            concentration_labels=concentration_labels,
        )

    async def _run_limited(self, items: list, worker, *, concurrency: int) -> list:
        semaphore = asyncio.Semaphore(concurrency)

        async def _run(item):
            async with semaphore:
                return await worker(item)

        return await asyncio.gather(*(_run(item) for item in items))

    def _filter_recent_papers(self, papers: list[Paper], *, cutoff: datetime) -> list[Paper]:
        return [paper for paper in papers if self._parse_datetime(paper.published) >= cutoff]

    def _batch_is_before_cutoff(self, papers: list[Paper], cutoff: datetime) -> bool:
        return bool(papers) and all(self._parse_datetime(paper.published) < cutoff for paper in papers)

    @staticmethod
    def _cutoff_datetime(years_back: int) -> datetime:
        years_back = max(1, years_back)
        return datetime.now(timezone.utc) - timedelta(days=365 * years_back)

    def _ingestion_cutoff(
        self,
        *,
        source_key: str,
        mode: str,
        years_back: int,
        overlap_days: int,
        reconcile_lookback_days: int,
    ) -> datetime:
        default_cutoff = self._cutoff_datetime(years_back)
        if mode == "seed":
            return default_cutoff

        source_label = self._source_labels[source_key]
        sync_state = self.database_service.read_source_sync_state(source_label)
        if sync_state and sync_state.high_watermark_published_at:
            watermark = self._parse_datetime(sync_state.high_watermark_published_at)
            lookback_days = overlap_days if mode == "incremental" else reconcile_lookback_days
            return max(default_cutoff, watermark - timedelta(days=lookback_days))

        fallback_days = 14 if mode == "incremental" else max(30, reconcile_lookback_days)
        return max(default_cutoff, datetime.now(timezone.utc) - timedelta(days=fallback_days))

    def _build_heatmap(self, cards: list[PaperCard]) -> tuple[list[HeatmapRow], list[str], list[str]]:
        category_labels = list(HUB_CATEGORY_LABELS)
        counts: dict[str, int] = {category: 0 for category in category_labels}

        for card in cards:
            matched = card.paper.hub_categories or ["General Multi-Agent Security"]
            for category in matched:
                if category in counts:
                    counts[category] += 1

        max_value = max(counts.values(), default=1) or 1
        heatmap_rows: list[HeatmapRow] = []
        for category in category_labels:
            count = counts.get(category, 0)
            intensity = count / max_value if max_value else 0.0
            if count >= max(3, round(max_value * 0.6)):
                status = "High concentration"
            elif count <= 1:
                status = "Gap / underexplored"
            else:
                status = "Emerging / moderate"
            heatmap_rows.append(
                HeatmapRow(
                    slug=self.slugify_category(category),
                    category=category,
                    count=count,
                    intensity=intensity,
                    status=status,
                )
            )

        heatmap_rows.sort(key=lambda row: (-row.count, row.category))

        concentration_labels = [row.category for row in heatmap_rows if row.status == "High concentration"]
        if not concentration_labels and heatmap_rows:
            concentration_labels = [
                item.category
                for item in sorted(heatmap_rows, key=lambda row: row.count, reverse=True)[:2]
                if item.count > 0
            ]
        gap_labels = [row.category for row in heatmap_rows if row.status == "Gap / underexplored"]
        if not gap_labels and heatmap_rows:
            gap_labels = [item.category for item in sorted(heatmap_rows, key=lambda row: row.count)[:2]]
        return heatmap_rows, gap_labels, concentration_labels

    def _build_landscape(
        self,
        cards: list[PaperCard],
        heatmap_rows: list[HeatmapRow],
    ) -> tuple[list[LandscapeNode], list[LandscapeEdge]]:
        width = 1100.0
        cluster_specs = {
            "High concentration": {"anchor": (265.0, 210.0), "color": "#BE5103"},
            "Emerging / moderate": {"anchor": (555.0, 250.0), "color": "#069494"},
            "Gap / underexplored": {"anchor": (845.0, 220.0), "color": "#7AC943"},
        }
        node_rows = heatmap_rows[:]

        if not node_rows:
            return [], []

        category_cards: dict[str, list[PaperCard]] = {row.category: [] for row in node_rows}
        for card in cards:
            for category in card.paper.hub_categories:
                if category in category_cards:
                    category_cards[category].append(card)

        nodes: list[LandscapeNode] = []
        groups: dict[str, list[HeatmapRow]] = {key: [] for key in cluster_specs}
        for row in node_rows:
            groups.setdefault(row.status, []).append(row)

        for status, rows in groups.items():
            if not rows:
                continue
            rows = sorted(rows, key=lambda item: (-item.count, item.category))
            anchor_x, anchor_y = cluster_specs[status]["anchor"]
            for index, row in enumerate(rows):
                angle = (-1.2) + ((index / max(1, len(rows))) * 5.0)
                ring = 58 + (index // 3) * 52
                jitter_x = (18 if index % 2 == 0 else -14)
                jitter_y = (12 if index % 3 == 0 else -10)
                x = anchor_x + math.cos(angle) * ring + jitter_x
                y = anchor_y + math.sin(angle) * ring + jitter_y
                radius = 34 + (row.intensity * 38)
                row_cards = category_cards.get(row.category, [])
                sources = sorted(
                    {
                        source
                        for card in row_cards
                        for source in (card.paper.merged_from_sources or [card.paper.source_name])
                    }
                )
                recent_threshold = datetime.now(timezone.utc) - timedelta(days=365)
                recent_count = sum(
                    1
                    for card in row_cards
                    if self._parse_datetime(card.paper.published) >= recent_threshold
                )
                nodes.append(
                    LandscapeNode(
                        slug=row.slug,
                        category=row.category,
                        label_lines=self._wrap_label(row.category, max_words_per_line=2),
                        count=row.count,
                        intensity=row.intensity,
                        status=row.status,
                        recent_count=recent_count,
                        source_count=len(sources),
                        source_summary=", ".join(sources[:4]) or "No source metadata",
                        sample_titles=[card.paper.title for card in row_cards[:2]],
                        x=round(x, 2),
                        y=round(y, 2),
                        radius=round(radius, 2),
                        color=cluster_specs[status]["color"],
                    )
                )

        return nodes, []

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(clamp_future_year(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    @staticmethod
    def slugify_category(value: str) -> str:
        return "-".join(part for part in "".join(char.lower() if char.isalnum() else " " for char in value).split() if part)

    @staticmethod
    def _wrap_label(value: str, *, max_words_per_line: int = 2) -> list[str]:
        words = value.split()
        if len(words) <= max_words_per_line:
            return [value]
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            current.append(word)
            if len(current) == max_words_per_line:
                lines.append(" ".join(current))
                current = []
        if current:
            lines.append(" ".join(current))
        return lines[:3]
