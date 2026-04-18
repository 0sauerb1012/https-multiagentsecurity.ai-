"""Coordinator for arXiv retrieval and summary generation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from math import ceil

from api.app.models import Paper, RankedPaper, ReviewedPaper
from api.app.services.arxiv import ArxivClient
from api.app.services.openai_agents import OpenAIAgentService
from api.app.services.ranking import build_rationale, rank_papers

from .categorization import HUB_CATEGORY_LABELS, PaperCategorizationService
from .crossref import CrossrefClient
from .dblp import DblpClient
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


@dataclass(frozen=True)
class PaperCard:
    paper: ReviewedPaper
    bullets: list[str]


@dataclass(frozen=True)
class HeatmapRow:
    slug: str
    category: str
    count: int
    intensity: float
    status: str


@dataclass(frozen=True)
class LandscapeNode:
    slug: str
    category: str
    label_lines: list[str]
    count: int
    intensity: float
    status: str
    recent_count: int
    source_count: int
    source_summary: str
    sample_titles: list[str]
    x: float
    y: float
    radius: float
    color: str


@dataclass(frozen=True)
class LandscapeEdge:
    source_slug: str
    target_slug: str
    x1: float
    y1: float
    x2: float
    y2: float
    weight: int
    opacity: float


@dataclass(frozen=True)
class ResearchHubResult:
    cards: list[PaperCard]
    feed_label: str
    tracked_topics: list[str]
    heatmap_rows: list[HeatmapRow]
    landscape_nodes: list[LandscapeNode]
    landscape_edges: list[LandscapeEdge]
    gap_labels: list[str]
    concentration_labels: list[str]


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

    async def fetch_latest_papers(
        self,
        *,
        limit: int = 12,
    ) -> ResearchHubResult:
        return await self._build_snapshot(limit=limit)

    async def fetch_area_papers(
        self,
        *,
        area_slug: str,
        limit: int = 36,
    ) -> tuple[str, list[PaperCard]]:
        snapshot = await self._build_snapshot(limit=limit)
        for row in snapshot.heatmap_rows:
            if row.slug == area_slug:
                cards = [card for card in snapshot.cards if row.category in card.paper.hub_categories]
                return row.category, cards
        raise ValueError("Unknown research area.")

    async def _build_snapshot(self, *, limit: int) -> ResearchHubResult:
        limit = max(1, min(limit, 60))
        topic_definitions = list(BROAD_AGENTIC_AI_TOPICS)
        per_topic_limit = max(8, ceil((limit * 3) / max(1, len(topic_definitions))) + 2)
        source_paper_sets = await asyncio.gather(
            *(self._load_topic_papers(topic, per_topic_limit=per_topic_limit) for topic in topic_definitions)
        )

        merged_candidates = self.merging_service.cluster_and_merge([paper for papers in source_paper_sets for paper in papers])

        if not merged_candidates:
            fallback_result = await self.arxiv_client.search(
                FALLBACK_QUERY,
                max_results=limit,
                sort_by="submittedDate",
                sort_order="descending",
            )
            merged_candidates = self.merging_service.cluster_and_merge(fallback_result.papers)

        filtered_papers = await self._filter_for_multi_agent_security(merged_candidates, limit=limit)
        newest_first = sorted(filtered_papers, key=lambda paper: self._parse_datetime(paper.published), reverse=True)[:limit]

        cards = await asyncio.gather(*(self._build_card(paper) for paper in newest_first))
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

    async def _load_topic_papers(self, topic: TopicDefinition, *, per_topic_limit: int) -> list[Paper]:
        arxiv_task = self.arxiv_client.search(
            topic.query,
            max_results=per_topic_limit,
            sort_by="submittedDate",
            sort_order="descending",
        )
        crossref_task = self.crossref_client.search(topic.query, rows=per_topic_limit)
        dblp_task = self.dblp_client.search(topic.query, limit=per_topic_limit)
        openalex_task = self.openalex_client.search(topic.query, per_page=per_topic_limit)
        semantic_scholar_task = self.semantic_scholar_client.search(topic.query, limit=per_topic_limit)
        arxiv_result, crossref_result, dblp_result, openalex_result, semantic_scholar_result = await asyncio.gather(
            arxiv_task,
            crossref_task,
            dblp_task,
            openalex_task,
            semantic_scholar_task,
            return_exceptions=True,
        )

        papers: list[Paper] = []
        if not isinstance(arxiv_result, Exception):
            papers.extend(arxiv_result.papers)
        if not isinstance(crossref_result, Exception):
            papers.extend(crossref_result.papers)
        if not isinstance(dblp_result, Exception):
            papers.extend(dblp_result.papers)
        if not isinstance(openalex_result, Exception):
            papers.extend(openalex_result.papers)
        if not isinstance(semantic_scholar_result, Exception):
            papers.extend(semantic_scholar_result.papers)
        return papers

    async def _filter_for_multi_agent_security(self, papers: list[Paper], *, limit: int) -> list[ReviewedPaper]:
        ranked = rank_papers(MULTI_AGENT_SECURITY_FIELD_TOPIC, papers)
        review_pool = ranked[: max(limit * 3, 18)]
        if self.agent_service.is_enabled():
            reviewed = await asyncio.gather(*(self._review_candidate(paper) for paper in review_pool))
        else:
            reviewed = [self._build_deterministic_review(paper) for paper in review_pool]

        accepted = [paper for paper in reviewed if paper.is_fit]
        if accepted:
            accepted.sort(key=lambda paper: (paper.fit_score, self._parse_datetime(paper.published)), reverse=True)
            return accepted

        fallback_ranked = [self._build_deterministic_review(paper) for paper in review_pool]
        fallback_ranked.sort(key=lambda paper: (paper.fit_score, self._parse_datetime(paper.published)), reverse=True)
        return [paper for paper in fallback_ranked if paper.is_fit][:limit]

    async def _review_candidate(self, paper: RankedPaper) -> ReviewedPaper:
        try:
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
        except Exception:
            return self._build_deterministic_review(paper)

    def _build_deterministic_review(self, paper: RankedPaper) -> ReviewedPaper:
        threshold = 2.8
        is_fit = paper.relevance_score >= threshold
        reviewer_notes = build_rationale(
            topic=MULTI_AGENT_SECURITY_FIELD_TOPIC,
            title=paper.title,
            summary=paper.summary,
            threshold=threshold,
            score=paper.relevance_score,
            accepted=is_fit,
        )
        return ReviewedPaper(
            **paper.model_dump(),
            is_fit=is_fit,
            fit_score=paper.relevance_score,
            reviewer_notes=reviewer_notes,
        )

    async def _build_card(self, paper: ReviewedPaper) -> PaperCard:
        categorized = paper.model_copy(update={"hub_categories": self.categorization_service.categorize(paper)})
        bullets = await self.summary_service.summarize(categorized)
        return PaperCard(paper=categorized, bullets=bullets)

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
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
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
