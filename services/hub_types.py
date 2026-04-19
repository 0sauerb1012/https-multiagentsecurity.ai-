"""Shared dataclasses for the research hub presentation layer."""

from __future__ import annotations

from dataclasses import dataclass

from api.app.models import ReviewedPaper


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
class LibraryCategoryGroup:
    slug: str
    category: str
    count: int
    cards: list[PaperCard]


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
