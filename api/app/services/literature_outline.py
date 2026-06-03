from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.models import LiteratureOutlineSection, LiteratureReviewOutlineResponse, ReviewedPaper
from app.services.exporters import build_apa_citation


@dataclass(frozen=True)
class OutlineInput:
    topic: str
    query_used: str
    total_candidates: int
    accepted_papers: int
    workflow_steps: list[str]
    sanity_report: list[str]
    papers: list[ReviewedPaper]


class LiteratureOutlineService:
    def build_outline(self, data: OutlineInput) -> LiteratureReviewOutlineResponse:
        accepted = [paper for paper in data.papers if paper.is_fit]
        grouped = self._group_papers(accepted)
        sections = [
            LiteratureOutlineSection(
                title="Introduction and Scope",
                overview=(
                    f"This review surveys {data.topic} using references drawn from the Zotero library. "
                    f"The outline emphasizes the accepted papers with the strongest fit scores."
                ),
                bullet_points=self._build_intro_points(data.topic, accepted),
            )
        ]

        for section_title, papers in grouped[:4]:
            sections.append(
                LiteratureOutlineSection(
                    title=section_title,
                    overview=self._build_section_overview(section_title, papers),
                    bullet_points=self._build_section_points(papers),
                )
            )

        sections.append(
            LiteratureOutlineSection(
                title="Synthesis and Research Gaps",
                overview=(
                    "The closing section should compare evidence across the accepted studies and identify the "
                    "methodological, empirical, or application gaps that remain."
                ),
                bullet_points=self._build_gap_points(accepted),
            )
        )

        bibliography = [build_apa_citation(paper) for paper in accepted]
        return LiteratureReviewOutlineResponse(
            topic=data.topic,
            outline_title=f"Literature Review Outline: {data.topic}",
            query_used=data.query_used,
            total_candidates=data.total_candidates,
            accepted_papers=data.accepted_papers,
            workflow_steps=[
                *data.workflow_steps,
                f"outline_agent used deterministic literature-review synthesis for {len(accepted)} accepted Zotero papers",
            ],
            sanity_report=data.sanity_report,
            sections=sections,
            bibliography=bibliography,
        )

    def _group_papers(self, papers: list[ReviewedPaper]) -> list[tuple[str, list[ReviewedPaper]]]:
        grouped: dict[str, list[ReviewedPaper]] = defaultdict(list)
        for paper in papers:
            label = self._section_label(paper)
            grouped[label].append(paper)

        ordered = []
        for label, items in grouped.items():
            ordered.append((label, sorted(items, key=lambda paper: paper.fit_score, reverse=True)))
        ordered.sort(key=lambda item: (len(item[1]), sum(p.fit_score for p in item[1])), reverse=True)
        return ordered

    def _section_label(self, paper: ReviewedPaper) -> str:
        if paper.primary_category:
            return f"Theme: {paper.primary_category}"
        if paper.categories:
            return f"Theme: {paper.categories[0]}"
        return "Theme: Core Literature"

    def _build_intro_points(self, topic: str, papers: list[ReviewedPaper]) -> list[str]:
        if not papers:
            return [f"The Zotero library did not contain accepted papers for {topic}."]
        citations = self._parenthetical_citations(papers[:3])
        return [
            f"Define the problem space and explain why {topic} matters {citations}.",
            f"State the review boundaries, corpus size, and inclusion criteria based on Zotero library screening {citations}.",
            "Preview the major themes that organize the remainder of the review.",
        ]

    def _build_section_overview(self, title: str, papers: list[ReviewedPaper]) -> str:
        citations = self._parenthetical_citations(papers[:2])
        return f"This section synthesizes the strongest accepted papers for {title.lower()} {citations}."

    def _build_section_points(self, papers: list[ReviewedPaper]) -> list[str]:
        points: list[str] = []
        for paper in papers[:3]:
            summary_point = (paper.key_points_summary or [paper.summary or "Discuss the paper's contribution."])[0]
            points.append(f"Discuss {paper.title} and its main contribution: {summary_point} {self._parenthetical_citations([paper])}.")
        if len(points) < 3:
            points.append("Compare how the studies in this theme align or disagree on methods, evidence, and limitations.")
        return points

    def _build_gap_points(self, papers: list[ReviewedPaper]) -> list[str]:
        if not papers:
            return ["Identify missing evidence, methods, or application settings once suitable papers are collected."]
        citations = self._parenthetical_citations(papers[:4])
        return [
            f"Compare the methodological strengths and weaknesses across the accepted literature {citations}.",
            "Identify which populations, datasets, or benchmarks remain under-studied.",
            "Conclude with the research questions that follow directly from the reviewed evidence.",
        ]

    def _parenthetical_citations(self, papers: list[ReviewedPaper]) -> str:
        citations = [self._short_citation(paper) for paper in papers]
        return f"({'; '.join(citations)})" if citations else ""

    def _short_citation(self, paper: ReviewedPaper) -> str:
        author = paper.authors[0].split()[-1] if paper.authors else "Unknown"
        year = paper.published[:4] if paper.published else "n.d."
        return f"{author}, {year}"
