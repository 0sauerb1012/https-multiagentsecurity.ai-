from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
import warnings

from langchain_openai import ChatOpenAI
from openai import APIError, RateLimitError
from pydantic import BaseModel, Field

from ..config import settings
from ..models import AgentSearchRequest, Paper


warnings.filterwarnings(
    "ignore",
    message=r"Pydantic serializer warnings:.*PydanticSerializationUnexpectedValue.*field_name='parsed'.*",
    category=UserWarning,
)


@dataclass
class SearchPlan:
    query: str
    notes: str


@dataclass
class ReviewDecision:
    is_fit: bool
    fit_score: float
    reviewer_notes: str


@dataclass
class ClassificationDecision:
    is_relevant: bool
    categories: list[str]
    confidence: float
    rationale: str


@dataclass
class PaperSummary:
    key_points_summary: list[str]


class SearchPlanSchema(BaseModel):
    query: str = Field(..., description="A valid arXiv search_query string.")
    notes: str = Field(..., description="Short explanation of how the query was formed.")


class ReviewDecisionSchema(BaseModel):
    is_fit: bool = Field(..., description="Whether the paper fits the requested topic.")
    fit_score: float = Field(..., ge=0.0, le=10.0, description="Fit score from 0 to 10.")
    reviewer_notes: str = Field(..., description="Brief justification for the decision.")


class PaperSummarySchema(BaseModel):
    key_points_summary: list[str] = Field(
        ...,
        min_length=5,
        max_length=10,
        description="Five to ten concise bullet points summarizing the paper's key points.",
    )


class ClassificationDecisionSchema(BaseModel):
    is_relevant: bool = Field(..., description="Whether this paper is relevant to the target field.")
    categories: list[str] = Field(
        ...,
        min_length=0,
        max_length=3,
        description="Up to three categories selected from the provided taxonomy only.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence from 0 to 1.")
    rationale: str = Field(..., description="Brief explanation for the chosen categories.")


class ChunkSummarySchema(BaseModel):
    chunk_bullets: list[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="Three to five bullet points capturing the important claims from this chunk.",
    )


class OpenAIAgentService:
    def __init__(self) -> None:
        self._search_llm = None
        self._review_llm = None
        self._classification_llm = None
        self._summary_llm = None
        self._chunk_summary_llm = None
        if settings.openai_api_key:
            search_model = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_search_model,
            )
            review_model = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_review_model,
            )
            summary_model = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_summary_model,
            )
            self._search_llm = search_model.with_structured_output(SearchPlanSchema, method="json_schema")
            self._review_llm = review_model.with_structured_output(ReviewDecisionSchema, method="json_schema")
            self._classification_llm = review_model.with_structured_output(ClassificationDecisionSchema, method="json_schema")
            self._summary_llm = summary_model.with_structured_output(PaperSummarySchema, method="json_schema")
            self._chunk_summary_llm = summary_model.with_structured_output(ChunkSummarySchema, method="json_schema")

    def is_enabled(self) -> bool:
        return self._search_llm is not None and self._review_llm is not None

    def summarizer_enabled(self) -> bool:
        return self._summary_llm is not None

    def classifier_enabled(self) -> bool:
        return self._classification_llm is not None

    async def plan_search(self, request: AgentSearchRequest, fallback_query: str) -> SearchPlan:
        if self._search_llm is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        prompt = (
            "You are a research search planner for arXiv.\n"
            "The query must be a valid arXiv search_query string using fields like all:\"...\" and cat:...\n"
            "Keep the query focused and concise.\n\n"
            f"Topic: {request.topic}\n"
            f"Categories: {', '.join(request.categories) or 'none'}\n"
            f"Include terms: {', '.join(request.include_terms) or 'none'}\n"
            f"Exclude terms: {', '.join(request.exclude_terms) or 'none'}\n"
            f"Max results: {request.max_results}\n"
            f"Fallback query: {fallback_query}\n"
        )
        response = await self._ainvoke_with_retry(self._search_llm, prompt)
        query = response.query.strip() or fallback_query
        notes = response.notes.strip() or "LangChain planner generated the arXiv query."
        return SearchPlan(query=query, notes=notes)

    async def review_paper(
        self,
        *,
        topic: str,
        min_fit_score: float,
        paper: Paper,
        lexical_score: float,
        lexical_rationale: str,
    ) -> ReviewDecision:
        if self._review_llm is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        prompt = (
            "You are a paper reviewer deciding whether an arXiv paper fits a research topic.\n"
            "fit_score must be a number from 0 to 10.\n"
            "Base the decision on the paper title, summary, categories, and the requested topic.\n\n"
            f"Topic: {topic}\n"
            f"Minimum fit score: {min_fit_score}\n"
            f"Paper title: {paper.title}\n"
            f"Paper summary: {paper.summary}\n"
            f"Paper categories: {', '.join(paper.categories)}\n"
            f"Lexical baseline score: {lexical_score}\n"
            f"Lexical baseline rationale: {lexical_rationale}\n"
        )
        response = await self._ainvoke_with_retry(self._review_llm, prompt)
        fit_score = max(0.0, min(10.0, float(response.fit_score)))
        return ReviewDecision(
            is_fit=bool(response.is_fit),
            fit_score=fit_score,
            reviewer_notes=response.reviewer_notes.strip() or "LangChain reviewer did not provide notes.",
        )

    async def summarize_paper(self, *, topic: str, paper: Paper, paper_text: str) -> PaperSummary:
        if self._summary_llm is None or self._chunk_summary_llm is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        chunks = self._chunk_text(paper_text)
        if len(chunks) == 1:
            notes = chunks[0]
        else:
            chunk_summaries = await self._summarize_chunks(topic=topic, paper=paper, chunks=chunks)
            notes = "\n".join(f"- {bullet}" for bullet in chunk_summaries)

        prompt = (
            "You are a research summarizer.\n"
            "Return 5 to 10 concise bullet points capturing the paper's key points.\n"
            "Cover the problem, method, experimental setup or evidence, and primary contributions.\n"
            "Do not mention that these are generated bullets.\n\n"
            f"Requested topic: {topic}\n"
            f"Paper title: {paper.title}\n"
            f"Paper categories: {', '.join(paper.categories)}\n"
            f"Paper abstract: {paper.summary}\n"
            f"Paper notes:\n{notes}\n"
        )
        response = await self._ainvoke_with_retry(self._summary_llm, prompt)
        return PaperSummary(
            key_points_summary=[bullet.strip() for bullet in response.key_points_summary if bullet.strip()],
        )

    async def classify_paper(
        self,
        *,
        topic: str,
        taxonomy: list[str],
        paper: Paper,
        reviewer_notes: str,
        fallback_categories: list[str],
    ) -> ClassificationDecision:
        if self._classification_llm is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        prompt = (
            "You are classifying a research paper into a fixed taxonomy for a multi-agent security website.\n"
            "Only choose categories from the provided taxonomy.\n"
            "Return at most three categories.\n"
            "If the paper is not relevant to the field, set is_relevant to false and return an empty categories list.\n\n"
            f"Target field: {topic}\n"
            f"Taxonomy: {', '.join(taxonomy)}\n"
            f"Paper title: {paper.title}\n"
            f"Paper summary: {paper.summary}\n"
            f"Paper categories: {', '.join(paper.categories)}\n"
            f"Reviewer notes: {reviewer_notes}\n"
            f"Fallback categories: {', '.join(fallback_categories) or 'none'}\n"
        )
        response = await self._ainvoke_with_retry(self._classification_llm, prompt)
        categories = [category for category in response.categories if category in taxonomy][:3]
        confidence = max(0.0, min(1.0, float(response.confidence)))
        return ClassificationDecision(
            is_relevant=bool(response.is_relevant),
            categories=categories,
            confidence=confidence,
            rationale=response.rationale.strip() or "Classifier did not provide a rationale.",
        )

    async def _summarize_chunks(self, *, topic: str, paper: Paper, chunks: list[str]) -> list[str]:
        semaphore = asyncio.Semaphore(2)

        async def _run(chunk: str, index: int) -> list[str]:
            async with semaphore:
                return await self._summarize_chunk(
                    topic=topic,
                    paper=paper,
                    chunk=chunk,
                    index=index,
                    total=len(chunks),
                )

        tasks = [_run(chunk, index) for index, chunk in enumerate(chunks, start=1)]
        results = await asyncio.gather(*tasks)
        bullets: list[str] = []
        for result in results:
            bullets.extend(result)
        return bullets

    async def _summarize_chunk(self, *, topic: str, paper: Paper, chunk: str, index: int, total: int) -> list[str]:
        prompt = (
            "You are reading one section of a research paper.\n"
            "Return 3 to 5 concise bullets for the important points in this section.\n\n"
            f"Requested topic: {topic}\n"
            f"Paper title: {paper.title}\n"
            f"Chunk {index} of {total}:\n{chunk}\n"
        )
        response = await self._ainvoke_with_retry(self._chunk_summary_llm, prompt)
        return [bullet.strip() for bullet in response.chunk_bullets if bullet.strip()]

    async def _ainvoke_with_retry(self, llm, prompt: str, *, max_attempts: int = 6):
        delay = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                return await llm.ainvoke(prompt)
            except RateLimitError as exc:
                if attempt == max_attempts:
                    raise
                wait_seconds = self._retry_delay_from_exception(exc, fallback=delay)
                await asyncio.sleep(wait_seconds)
                delay = min(delay * 2, 20.0)
            except APIError as exc:
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * 2, 20.0)

    @staticmethod
    def _retry_delay_from_exception(exc: Exception, *, fallback: float) -> float:
        message = str(exc)
        match = re.search(r"try again in ([0-9]+)ms", message, re.IGNORECASE)
        if match:
            return max(float(match.group(1)) / 1000.0, 0.5)
        match = re.search(r"try again in ([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
        if match:
            return max(float(match.group(1)), 0.5)
        return fallback

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        chunk_size = settings.paper_text_chunk_chars
        normalized = " ".join(text.split())
        return [normalized[i : i + chunk_size] for i in range(0, len(normalized), chunk_size)] or [normalized]
