"""Paper summarization utilities for the local research hub."""

from __future__ import annotations

import re
from collections import Counter

from api.app.models import Paper
from api.app.services.openai_agents import OpenAIAgentService
from api.app.services.paper_content import PaperContentService


class PaperSummaryService:
    """Summarize papers with OpenAI only."""

    def __init__(self) -> None:
        self.agent_service = OpenAIAgentService()
        self.paper_content_service = PaperContentService()
        self._keywords = {
            "agent",
            "agents",
            "multi-agent",
            "security",
            "risk",
            "trust",
            "prompt",
            "injection",
            "autonomous",
            "llm",
            "tool",
            "policy",
            "attack",
            "defense",
        }

    async def summarize(self, paper: Paper) -> list[str]:
        if not self.agent_service.summarizer_enabled():
            raise RuntimeError("OpenAI summarization is required for this pipeline. Configure a working OPENAI_API_KEY.")

        source_text = await self._load_source_text(paper)
        try:
            summary = await self.agent_service.summarize_paper(
                topic="multi-agent security research",
                paper=paper,
                paper_text=source_text,
            )
            bullets = [self._normalize_bullet(point) for point in summary.key_points_summary if point.strip()]
            if bullets:
                return bullets[:5]
        except Exception:
            pass
        return self._build_extractive_summary(source_text, paper.summary)

    async def _load_source_text(self, paper: Paper) -> str:
        if paper.pdf_url:
            try:
                return await self.paper_content_service.fetch_text(paper)
            except Exception:
                pass
        return paper.summary

    def _build_extractive_summary(self, source_text: str, abstract_text: str) -> list[str]:
        text = source_text or abstract_text
        sentences = self._split_sentences(text)
        if not sentences:
            return ["Summary unavailable because no extractable text was returned."]

        keyword_scores = self._keyword_scores(text)
        ranked_sentences = sorted(
            sentences,
            key=lambda sentence: self._sentence_score(sentence, keyword_scores),
            reverse=True,
        )

        bullets: list[str] = []
        for sentence in ranked_sentences:
            normalized = self._normalize_bullet(sentence)
            if normalized not in bullets:
                bullets.append(normalized)
            if len(bullets) == 5:
                break

        if len(bullets) < 3:
            for sentence in sentences:
                normalized = self._normalize_bullet(sentence)
                if normalized not in bullets:
                    bullets.append(normalized)
                if len(bullets) == 3:
                    break

        return bullets[:5]

    def _keyword_scores(self, text: str) -> Counter[str]:
        tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())
        filtered = [token for token in tokens if token in self._keywords]
        return Counter(filtered)

    def _sentence_score(self, sentence: str, keyword_scores: Counter[str]) -> float:
        tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", sentence.lower())
        score = sum(keyword_scores.get(token, 0) + (2 if token in self._keywords else 0) for token in tokens)
        score += max(0, 180 - len(sentence)) / 180
        return score

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        candidates = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
        clean_sentences: list[str] = []
        for sentence in candidates:
            normalized = " ".join(sentence.split())
            if len(normalized) >= 40:
                clean_sentences.append(normalized)
        return clean_sentences

    @staticmethod
    def _normalize_bullet(value: str) -> str:
        normalized = " ".join(value.split()).lstrip("-• ").strip()
        if len(normalized) > 260:
            normalized = normalized[:257].rstrip() + "..."
        return normalized
