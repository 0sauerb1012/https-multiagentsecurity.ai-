"""Categorize papers for the research hub.

This layer is source-agnostic so future inputs can reuse the same category pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from api.app.models import Paper


@dataclass(frozen=True)
class CategoryRule:
    label: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class HeuristicClassification:
    categories: list[str]
    is_relevant: bool
    confidence: float
    rationale: str


HUB_CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule("Prompt Injection", ("prompt injection", "instruction hijack", "jailbreak", "indirect prompt injection")),
    CategoryRule("Trust and Identity", ("trust", "identity", "authentication", "authorization", "verification")),
    CategoryRule("Agent-to-Agent Communication", ("agent-to-agent", "agent communication", "multi-agent communication", "negotiation", "coordination")),
    CategoryRule("Orchestration Risk", ("orchestration", "planner", "delegation", "tool use", "function calling", "supervisor")),
    CategoryRule("Memory Poisoning", ("memory poisoning", "memory", "context poisoning", "retrieval poisoning", "context corruption")),
    CategoryRule("Governance and Policy", ("governance", "policy", "oversight", "assurance", "compliance")),
    CategoryRule("Benchmarks and Evaluation", ("benchmark", "evaluation", "dataset", "measurement", "red team")),
)

HUB_CATEGORY_LABELS: tuple[str, ...] = tuple(rule.label for rule in HUB_CATEGORY_RULES)

RELEVANCE_KEYWORDS: tuple[str, ...] = (
    "agent",
    "multi-agent",
    "autonomous agent",
    "agentic",
    "llm agent",
    "prompt injection",
    "agent orchestration",
    "function calling",
    "agent memory",
    "agent communication",
    "tool use",
)


class PaperCategorizationService:
    """Assign lightweight hub categories from title, abstract, and source metadata.

    Extension points:
    - replace keyword rules with model-based taxonomy mapping
    - merge source-native tags with hub taxonomy confidence scores
    - attach multi-label explanations for downstream filtering and visualization
    """

    def categorize(self, paper: Paper) -> list[str]:
        return self.classify(paper).categories

    def classify(self, paper: Paper) -> HeuristicClassification:
        haystack = self._normalize(" ".join([paper.title, paper.summary, " ".join(paper.categories)]))
        matched_categories: list[tuple[str, int, list[str]]] = []

        for rule in HUB_CATEGORY_RULES:
            hits = [keyword for keyword in rule.keywords if keyword in haystack]
            if hits:
                matched_categories.append((rule.label, len(hits), hits))

        matched_categories.sort(key=lambda item: (-item[1], item[0]))
        categories = [label for label, _, _ in matched_categories[:3]]
        broad_hits = [keyword for keyword in RELEVANCE_KEYWORDS if keyword in haystack]
        is_relevant = bool(categories) or len(broad_hits) >= 2

        if not categories:
            confidence = 0.0 if not is_relevant else 0.35
            rationale = (
                "No taxonomy keywords matched."
                if not is_relevant
                else f"Broad MAS relevance detected from: {', '.join(broad_hits[:4])}."
            )
            return HeuristicClassification(
                categories=[],
                is_relevant=is_relevant,
                confidence=confidence,
                rationale=rationale,
            )

        confidence = min(0.95, 0.45 + (0.12 * sum(score for _, score, _ in matched_categories[:3])) + (0.03 * len(broad_hits)))
        rationale_parts = [
            f"{label}: {', '.join(hits[:3])}"
            for label, _, hits in matched_categories[:3]
        ]
        if broad_hits:
            rationale_parts.append(f"broad relevance: {', '.join(broad_hits[:4])}")
        return HeuristicClassification(
            categories=categories,
            is_relevant=True,
            confidence=confidence,
            rationale="; ".join(rationale_parts),
        )

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        return normalized
