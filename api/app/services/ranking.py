from __future__ import annotations

import math
import re
from collections import Counter

from ..models import Paper, RankedPaper


TOKEN_RE = re.compile(r"[a-z0-9]+")


def rank_papers(topic: str, papers: list[Paper]) -> list[RankedPaper]:
    topic_tokens = _tokenize(topic)
    if not topic_tokens:
        return [
            RankedPaper(**paper.model_dump(), relevance_score=0.0, rationale="No topic tokens available.")
            for paper in papers
        ]

    ranked: list[RankedPaper] = []
    for paper in papers:
        title_tokens = _tokenize(paper.title)
        summary_tokens = _tokenize(paper.summary)
        score = _overlap_score(topic_tokens, title_tokens, summary_tokens)
        rationale = _build_rationale(topic_tokens, title_tokens, summary_tokens)
        ranked.append(RankedPaper(**paper.model_dump(), relevance_score=round(score, 3), rationale=rationale))

    ranked.sort(key=lambda paper: paper.relevance_score, reverse=True)
    return ranked


def build_rationale(topic: str, title: str, summary: str, *, threshold: float, score: float, accepted: bool) -> str:
    topic_tokens = _tokenize(topic)
    title_tokens = _tokenize(title)
    summary_tokens = _tokenize(summary)
    overlap = _build_rationale(topic_tokens, title_tokens, summary_tokens)
    verdict = "accepted" if accepted else "rejected"
    return f"{verdict} at score {score:.3f} against threshold {threshold:.3f}; {overlap}"


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _overlap_score(topic_tokens: list[str], title_tokens: list[str], summary_tokens: list[str]) -> float:
    title_counts = Counter(title_tokens)
    summary_counts = Counter(summary_tokens)
    score = 0.0

    for token in topic_tokens:
        score += 3.0 * min(title_counts[token], 1)
        score += 1.0 * min(summary_counts[token], 1)

    normalization = math.sqrt(len(set(topic_tokens))) or 1.0
    return score / normalization


def _build_rationale(topic_tokens: list[str], title_tokens: list[str], summary_tokens: list[str]) -> str:
    title_hits = [token for token in sorted(set(topic_tokens)) if token in title_tokens]
    summary_hits = [token for token in sorted(set(topic_tokens)) if token in summary_tokens and token not in title_hits]

    parts: list[str] = []
    if title_hits:
        parts.append(f"title matches: {', '.join(title_hits[:5])}")
    if summary_hits:
        parts.append(f"summary matches: {', '.join(summary_hits[:5])}")
    if not parts:
        return "Weak lexical overlap; included because it matched the arXiv query."
    return "; ".join(parts)
