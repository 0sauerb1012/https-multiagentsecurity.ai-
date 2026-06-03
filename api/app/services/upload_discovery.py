from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import UploadFile

from app.models import AgentSearchResponse, Paper, RankedPaper, ReviewedPaper
from app.services.openai_agents import OpenAIAgentService
from app.services.paper_content import ExtractedPaperContent, PaperContentService
from app.services.ranking import build_rationale, rank_papers
from app.services.sanity import SanityCheckService
from app.services.zotero_rdf import parse_zotero_rdf


@dataclass(frozen=True)
class UploadDiscoveryRequest:
    topic: str | None
    min_fit_score: float
    include_rejected: bool
    score_against_topic: bool = True


class UploadDiscoveryService:
    def __init__(self) -> None:
        self.agent_service = OpenAIAgentService()
        self.paper_content_service = PaperContentService()
        self.sanity_service = SanityCheckService()

    async def run(self, request: UploadDiscoveryRequest, files: list[UploadFile]) -> AgentSearchResponse:
        extracted = await self._extract_candidates(files)
        query_used = "uploaded_batch_analyze" if request.score_against_topic else "uploaded_batch_organize"
        return await self.run_on_extracted(
            request,
            extracted,
            query_used=query_used,
            source_description="uploaded files",
        )

    async def run_on_extracted(
        self,
        request: UploadDiscoveryRequest,
        extracted: list[tuple[Paper, ExtractedPaperContent]],
        *,
        query_used: str,
        source_description: str,
        progress_callback: Callable[[int, str], Awaitable[None] | None] | None = None,
    ) -> AgentSearchResponse:
        papers = [paper for paper, _ in extracted]
        paper_text_by_id = {paper.id: content.text for paper, content in extracted}
        ranked = rank_papers(request.topic or "", papers)
        await self._report_progress(progress_callback, 78, f"Scored {len(papers)} references")

        if not request.score_against_topic:
            reviewed_papers = self._organize_without_scoring(ranked)
            review_step = f"review_agent skipped topic scoring and accepted {len(reviewed_papers)} uploaded papers for organization"
        elif self.agent_service.is_enabled():
            reviewed_papers = await self._review_with_openai(request, ranked)
            review_step = f"review_agent used LangChain/OpenAI reviewer for {len(reviewed_papers)} uploaded papers"
        else:
            reviewed_papers = self._review_deterministically(request, ranked)
            review_step = f"review_agent used deterministic reviewer for {len(reviewed_papers)} uploaded papers"

        accepted_count = sum(paper.is_fit for paper in reviewed_papers)
        if accepted_count == 0:
            summarized_papers = reviewed_papers
            summary_step = "summary_agent skipped summarization because no uploaded papers were accepted"
            await self._report_progress(progress_callback, 95, "No accepted references to summarize")
        elif self.agent_service.summarizer_enabled():
            await self._report_progress(progress_callback, 88, f"Summarizing {accepted_count} accepted references")
            summarized_papers = await self._summarize_with_openai(
                request.topic or "No topic provided. Summarize these uploaded references for organization.",
                reviewed_papers,
                paper_text_by_id,
            )
            summary_step = f"summary_agent used LangChain/OpenAI summarizer for {accepted_count} accepted uploaded papers"
        else:
            await self._report_progress(progress_callback, 88, f"Building deterministic summaries for {accepted_count} accepted references")
            summarized_papers = self._summarize_deterministically(reviewed_papers)
            summary_step = f"summary_agent used deterministic summarizer for {accepted_count} accepted uploaded papers"

        accepted = [paper for paper in summarized_papers if paper.is_fit]
        visible = summarized_papers if request.include_rejected else accepted
        sanity_result = self.sanity_service.audit(
            topic=request.topic,
            query_used=query_used,
            total_candidates=len(papers),
            papers=summarized_papers,
            requires_query_validation=False,
            organization_mode=not request.score_against_topic,
        )

        return AgentSearchResponse(
            topic=request.topic or "",
            query_used=query_used,
            total_candidates=len(papers),
            accepted_papers=len(accepted),
            workflow_steps=[
                f"upload_agent: read {source_description} and extract text candidates",
                "review_agent: score each uploaded paper and decide whether it fits the topic"
                if request.score_against_topic
                else "review_agent: skip topic scoring and organize uploaded papers for summary/export",
                "summary_agent: summarize accepted uploaded files into key bullet points",
                "sanity_agent: validate uploaded extraction, review ordering, and summary coverage",
                f"upload_agent processed {len(papers)} references from {source_description}",
                review_step,
                summary_step,
                f"sanity_agent completed {sanity_result.status} audit for {len(summarized_papers)} reviewed papers",
            ],
            sanity_report=sanity_result.report,
            papers=visible,
        )

    async def _report_progress(
        self,
        callback: Callable[[int, str], Awaitable[None] | None] | None,
        progress: int,
        message: str,
    ) -> None:
        if callback is None:
            return
        result = callback(progress, message)
        if result is not None:
            await result

    async def _extract_candidates(self, files: list[UploadFile]) -> list[tuple[Paper, ExtractedPaperContent]]:
        candidates: list[tuple[Paper, ExtractedPaperContent]] = []
        for index, file in enumerate(files, start=1):
            filename = file.filename or f"upload-{index}"
            content = await file.read()
            suffix = Path(filename).suffix.lower()
            if suffix == ".pdf":
                extracted = self.paper_content_service.extract_uploaded_paper(content, filename=filename)
                paper = self._build_uploaded_paper(index=index, filename=filename, extracted=extracted)
                candidates.append((paper, extracted))
            elif suffix == ".rdf":
                rdf_entries = parse_zotero_rdf(content, filename=filename)
                for rdf_entry in rdf_entries:
                    candidates.append(
                        (
                            rdf_entry.paper,
                            ExtractedPaperContent(
                                title=rdf_entry.paper.title,
                                summary=rdf_entry.paper.summary,
                                text=rdf_entry.text,
                                authors=rdf_entry.paper.authors,
                            ),
                        )
                    )
            await file.close()
        return candidates

    def _build_uploaded_paper(self, *, index: int, filename: str, extracted: ExtractedPaperContent) -> Paper:
        stem = Path(filename).stem.strip() or f"upload-{index}"
        return Paper(
            id=f"upload-{index}-{stem.lower().replace(' ', '-')}",
            title=extracted.title,
            summary=extracted.summary,
            published="",
            updated="",
            authors=extracted.authors,
            categories=["uploaded-pdf"],
            primary_category="uploaded-pdf",
            paper_url="",
            pdf_url="",
        )

    async def _review_with_openai(
        self,
        request: UploadDiscoveryRequest,
        ranked: list[RankedPaper],
    ) -> list[ReviewedPaper]:
        tasks = [self._review_single_paper(request, paper) for paper in ranked]
        reviewed_papers = await asyncio.gather(*tasks)
        reviewed_papers.sort(key=lambda paper: paper.fit_score, reverse=True)
        return reviewed_papers

    async def _review_single_paper(self, request: UploadDiscoveryRequest, paper: RankedPaper) -> ReviewedPaper:
        try:
            decision = await self.agent_service.review_paper(
                topic=request.topic,
                min_fit_score=request.min_fit_score,
                paper=paper,
                lexical_score=paper.relevance_score,
                lexical_rationale=paper.rationale,
            )
        except Exception:
            return self._build_deterministic_review(request, paper)

        return ReviewedPaper(
            **paper.model_dump(),
            is_fit=decision.is_fit,
            fit_score=decision.fit_score,
            reviewer_notes=decision.reviewer_notes,
        )

    def _review_deterministically(
        self,
        request: UploadDiscoveryRequest,
        ranked: list[RankedPaper],
    ) -> list[ReviewedPaper]:
        reviewed_papers = [self._build_deterministic_review(request, paper) for paper in ranked]
        reviewed_papers.sort(key=lambda paper: paper.fit_score, reverse=True)
        return reviewed_papers

    def _build_deterministic_review(self, request: UploadDiscoveryRequest, paper: RankedPaper) -> ReviewedPaper:
        is_fit = paper.relevance_score >= request.min_fit_score
        reviewer_notes = build_rationale(
            topic=request.topic or "",
            title=paper.title,
            summary=paper.summary,
            threshold=request.min_fit_score,
            score=paper.relevance_score,
            accepted=is_fit,
        )
        return ReviewedPaper(
            **paper.model_dump(),
            is_fit=is_fit,
            fit_score=paper.relevance_score,
            reviewer_notes=reviewer_notes,
        )

    def _organize_without_scoring(self, ranked: list[RankedPaper]) -> list[ReviewedPaper]:
        reviewed_papers = [
            ReviewedPaper(
                **paper.model_dump(),
                is_fit=True,
                fit_score=0.0,
                reviewer_notes="Accepted for organization-only mode. No topic scoring was applied.",
            )
            for paper in ranked
        ]
        reviewed_papers.sort(key=lambda paper: paper.title.lower())
        return reviewed_papers

    async def _summarize_with_openai(
        self,
        topic: str,
        reviewed_papers: list[ReviewedPaper],
        paper_text_by_id: dict[str, str],
    ) -> list[ReviewedPaper]:
        tasks = [self._summarize_single_paper(topic, paper, paper_text_by_id) for paper in reviewed_papers]
        return await asyncio.gather(*tasks)

    async def _summarize_single_paper(
        self,
        topic: str,
        paper: ReviewedPaper,
        paper_text_by_id: dict[str, str],
    ) -> ReviewedPaper:
        if not paper.is_fit:
            return paper

        try:
            summary = await self.agent_service.summarize_paper(
                topic=topic,
                paper=paper,
                paper_text=paper_text_by_id.get(paper.id, paper.summary),
            )
            return ReviewedPaper(
                **paper.model_dump(exclude={"key_points_summary"}),
                key_points_summary=summary.key_points_summary,
            )
        except Exception:
            return ReviewedPaper(
                **paper.model_dump(exclude={"key_points_summary"}),
                key_points_summary=self._build_deterministic_summary(paper),
            )

    def _summarize_deterministically(self, reviewed_papers: list[ReviewedPaper]) -> list[ReviewedPaper]:
        summarized: list[ReviewedPaper] = []
        for paper in reviewed_papers:
            if paper.is_fit:
                summarized.append(
                    ReviewedPaper(
                        **paper.model_dump(exclude={"key_points_summary"}),
                        key_points_summary=self._build_deterministic_summary(paper),
                    )
                )
            else:
                summarized.append(paper)
        return summarized

    def _build_deterministic_summary(self, paper: ReviewedPaper) -> list[str]:
        cleaned = " ".join(paper.summary.split())
        if not cleaned:
            return [
                f"{paper.title} appears relevant, but no extractable uploaded file text was available.",
                f"Reviewer signal: {paper.reviewer_notes}",
                "Source: uploaded file batch.",
                "Published date was not available from the uploaded file.",
                "No additional full-text bullet points were available.",
            ]

        sentences = [sentence.strip() for sentence in cleaned.split(". ") if sentence.strip()]
        bullets = [f"Organization note: {paper.reviewer_notes}" if paper.fit_score == 0.0 else f"Topic fit: {paper.reviewer_notes}"]
        bullets.extend(sentences[:4])
        while len(bullets) < 5:
            bullets.append("Paper metadata: uploaded PDF with limited structured metadata")
        return [bullet if bullet.endswith(".") else f"{bullet}." for bullet in bullets[:5]]
