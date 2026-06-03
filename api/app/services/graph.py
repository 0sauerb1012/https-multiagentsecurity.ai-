from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.models import AgentSearchRequest, AgentSearchResponse, Paper, RankedPaper, ReviewedPaper
from app.services.arxiv import ArxivClient, build_query
from app.services.openai_agents import OpenAIAgentService
from app.services.paper_content import PaperContentService
from app.services.ranking import build_rationale, rank_papers
from app.services.sanity import SanityCheckService


class DiscoveryState(TypedDict, total=False):
    request: AgentSearchRequest
    query: str
    candidates: list[Paper]
    reviewed_papers: list[ReviewedPaper]
    workflow_steps: list[str]
    sanity_report: list[str]


class PaperDiscoveryGraph:
    def __init__(self, arxiv_client: ArxivClient) -> None:
        self.arxiv_client = arxiv_client
        self.agent_service = OpenAIAgentService()
        self.paper_content_service = PaperContentService()
        self.sanity_service = SanityCheckService()
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(DiscoveryState)
        graph.add_node("search_agent", self._search_agent)
        graph.add_node("review_agent", self._review_agent)
        graph.add_node("summary_agent", self._summary_agent)
        graph.add_node("sanity_agent", self._sanity_agent)
        graph.add_edge(START, "search_agent")
        graph.add_edge("search_agent", "review_agent")
        graph.add_edge("review_agent", "summary_agent")
        graph.add_edge("summary_agent", "sanity_agent")
        graph.add_edge("sanity_agent", END)
        return graph.compile()

    async def run(self, request: AgentSearchRequest) -> AgentSearchResponse:
        state = await self._graph.ainvoke(
            {
                "request": request,
                "workflow_steps": [
                    "search_agent: build a focused arXiv query and fetch candidate papers",
                    "review_agent: score each candidate and decide whether it fits the topic",
                    "summary_agent: read accepted papers and produce 5-10 bullet points for each",
                    "sanity_agent: validate query construction, review ordering, and summary coverage",
                ],
            }
        )
        reviewed_papers = state["reviewed_papers"]
        accepted = [paper for paper in reviewed_papers if paper.is_fit]
        visible = reviewed_papers if request.include_rejected else accepted

        return AgentSearchResponse(
            topic=request.topic,
            query_used=state["query"],
            total_candidates=len(state["candidates"]),
            accepted_papers=len(accepted),
            workflow_steps=state["workflow_steps"],
            sanity_report=state["sanity_report"],
            papers=visible,
        )

    async def _search_agent(self, state: DiscoveryState) -> DiscoveryState:
        request = state["request"]
        fallback_query = build_query(
            request.topic,
            categories=request.categories,
            include_terms=request.include_terms,
            exclude_terms=request.exclude_terms,
        )
        query = fallback_query
        step_note = "search_agent used deterministic query construction"

        if self.agent_service.is_enabled():
            try:
                plan = await self.agent_service.plan_search(request, fallback_query)
                query = plan.query
                step_note = f"search_agent used LangChain/OpenAI planner: {plan.notes}"
            except Exception as exc:
                step_note = f"search_agent fell back to deterministic query construction after LangChain/OpenAI error: {exc}"

        result = await self.arxiv_client.search(
            query,
            max_results=request.max_results,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )
        return {
            "query": query,
            "candidates": result.papers,
            "workflow_steps": [
                *state["workflow_steps"],
                step_note,
                f"search_agent fetched {len(result.papers)} papers using query: {query}",
            ],
        }

    async def _review_agent(self, state: DiscoveryState) -> DiscoveryState:
        request = state["request"]
        ranked = rank_papers(request.topic, state["candidates"])
        if self.agent_service.is_enabled():
            reviewed_papers = await self._review_with_openai(request, ranked)
            review_step = f"review_agent used LangChain/OpenAI reviewer for {len(reviewed_papers)} candidates"
        else:
            reviewed_papers = self._review_deterministically(request, ranked)
            review_step = f"review_agent used deterministic reviewer for {len(reviewed_papers)} candidates"

        return {
            "reviewed_papers": reviewed_papers,
            "workflow_steps": [
                *state["workflow_steps"],
                review_step,
                f"review_agent accepted {sum(paper.is_fit for paper in reviewed_papers)} of {len(reviewed_papers)} candidates",
            ],
        }

    async def _summary_agent(self, state: DiscoveryState) -> DiscoveryState:
        request = state["request"]
        reviewed_papers = state["reviewed_papers"]
        accepted_count = sum(paper.is_fit for paper in reviewed_papers)
        if accepted_count == 0:
            return {
                "reviewed_papers": reviewed_papers,
                "workflow_steps": [
                    *state["workflow_steps"],
                    "summary_agent skipped summarization because no papers were accepted",
                ],
            }

        if self.agent_service.summarizer_enabled():
            summarized_papers = await self._summarize_with_openai(request, reviewed_papers)
            summary_step = f"summary_agent used LangChain/OpenAI summarizer for {accepted_count} accepted papers"
        else:
            summarized_papers = self._summarize_deterministically(reviewed_papers)
            summary_step = f"summary_agent used deterministic summarizer for {accepted_count} accepted papers"

        return {
            "reviewed_papers": summarized_papers,
            "workflow_steps": [
                *state["workflow_steps"],
                summary_step,
            ],
        }

    async def _sanity_agent(self, state: DiscoveryState) -> DiscoveryState:
        request = state["request"]
        reviewed_papers = state["reviewed_papers"]
        sanity_result = self.sanity_service.audit(
            topic=request.topic,
            query_used=state["query"],
            total_candidates=len(state["candidates"]),
            papers=reviewed_papers,
            requires_query_validation=True,
        )
        return {
            "sanity_report": sanity_result.report,
            "workflow_steps": [
                *state["workflow_steps"],
                f"sanity_agent completed {sanity_result.status} audit for {len(reviewed_papers)} reviewed papers",
            ],
        }

    async def _review_with_openai(
        self,
        request: AgentSearchRequest,
        ranked: list[RankedPaper],
    ) -> list[ReviewedPaper]:
        tasks = [
            self._review_single_paper(request, paper)
            for paper in ranked
        ]
        reviewed_papers = await asyncio.gather(*tasks)
        reviewed_papers.sort(key=lambda paper: paper.fit_score, reverse=True)
        return reviewed_papers

    async def _review_single_paper(self, request: AgentSearchRequest, paper: RankedPaper) -> ReviewedPaper:
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

    def _review_deterministically(self, request: AgentSearchRequest, ranked: list[RankedPaper]) -> list[ReviewedPaper]:
        reviewed_papers = [self._build_deterministic_review(request, paper) for paper in ranked]
        reviewed_papers.sort(key=lambda paper: paper.fit_score, reverse=True)
        return reviewed_papers

    def _build_deterministic_review(self, request: AgentSearchRequest, paper: RankedPaper) -> ReviewedPaper:
        is_fit = paper.relevance_score >= request.min_fit_score
        reviewer_notes = build_rationale(
            topic=request.topic,
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

    async def _summarize_with_openai(
        self,
        request: AgentSearchRequest,
        reviewed_papers: list[ReviewedPaper],
    ) -> list[ReviewedPaper]:
        tasks = [
            self._summarize_single_paper(request.topic, paper)
            for paper in reviewed_papers
        ]
        return await asyncio.gather(*tasks)

    async def _summarize_single_paper(self, topic: str, paper: ReviewedPaper) -> ReviewedPaper:
        if not paper.is_fit:
            return paper

        try:
            paper_text = await self.paper_content_service.fetch_text(paper)
            summary = await self.agent_service.summarize_paper(topic=topic, paper=paper, paper_text=paper_text)
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
                f"{paper.title} appears relevant, but the PDF text could not be extracted.",
                f"Reviewer signal: {paper.reviewer_notes}",
                f"Primary category: {paper.primary_category or 'unknown'}.",
                f"Published: {paper.published[:10] if paper.published else 'unknown'}.",
                "No additional full-text bullet points were available.",
            ]

        sentences = [sentence.strip() for sentence in cleaned.split(". ") if sentence.strip()]
        bullets = [f"Topic fit: {paper.reviewer_notes}"]
        bullets.extend(sentences[:4])
        while len(bullets) < 5:
            bullets.append(f"Paper metadata: {paper.primary_category or 'unknown category'} by {', '.join(paper.authors[:3])}")
        return [bullet if bullet.endswith(".") else f"{bullet}." for bullet in bullets[:5]]
