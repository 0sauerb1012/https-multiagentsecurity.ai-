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


HUB_CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule("Prompt Injection", ("prompt injection", "instruction hijack", "jailbreak")),
    CategoryRule("Agent Coordination", ("coordination", "cooperation", "collusion", "negotiation")),
    CategoryRule("Trust and Governance", ("trust", "governance", "assurance", "oversight", "policy")),
    CategoryRule("Tool Misuse", ("tool use", "tool misuse", "function calling", "api misuse")),
    CategoryRule("Memory and Context Risks", ("memory", "context", "shared environment", "shared memory")),
    CategoryRule("Autonomous Agent Safety", ("autonomous", "planning", "planner", "executor", "safety")),
    CategoryRule("Evaluation and Benchmarks", ("benchmark", "evaluation", "dataset", "measurement")),
    CategoryRule("Defense and Mitigation", ("defense", "mitigation", "guardrail", "detection")),
)

HUB_CATEGORY_LABELS: tuple[str, ...] = tuple(rule.label for rule in HUB_CATEGORY_RULES)


class PaperCategorizationService:
    """Assign lightweight hub categories from title, abstract, and source metadata.

    Extension points:
    - replace keyword rules with model-based taxonomy mapping
    - merge source-native tags with hub taxonomy confidence scores
    - attach multi-label explanations for downstream filtering and visualization
    """

    def categorize(self, paper: Paper) -> list[str]:
        haystack = self._normalize(" ".join([paper.title, paper.summary, " ".join(paper.categories)]))
        matches = [rule.label for rule in HUB_CATEGORY_RULES if any(keyword in haystack for keyword in rule.keywords)]

        if not matches and paper.primary_category:
            matches.append(f"Domain: {paper.primary_category}")
        if not matches and paper.categories:
            matches.append(f"Domain: {paper.categories[0]}")
        if not matches:
            matches.append("General Multi-Agent Security")

        return matches[:3]

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        return normalized
