"""Broad retrieval topics plus fixed field framing for the research hub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicDefinition:
    label: str
    query: str


# Broad retrieval first, then reviewer filtering for the actual field.
BROAD_AGENTIC_AI_TOPICS: tuple[TopicDefinition, ...] = (
    TopicDefinition(
        label="Agentic AI systems",
        query='all:"agentic AI" OR all:"agentic systems"',
    ),
    TopicDefinition(
        label="AI agents",
        query='all:"AI agent" OR all:"AI agents"',
    ),
    TopicDefinition(
        label="LLM agents",
        query='all:"LLM agent" OR all:"LLM agents"',
    ),
    TopicDefinition(
        label="Multi-agent systems",
        query='all:"multi-agent system" OR all:"multi-agent systems" OR all:"multi agent system"',
    ),
    TopicDefinition(
        label="Autonomous agents",
        query='all:"autonomous agent" OR all:"autonomous agents"',
    ),
)


MULTI_AGENT_SECURITY_FIELD_TOPIC = (
    "multi-agent security research: security risks, attacks, defenses, trust boundaries, "
    "prompt injection, collusion, coordination failures, shared-memory or shared-environment "
    "manipulation, tool misuse, governance, and control problems in systems composed of "
    "multiple interacting AI agents"
)


FIELD_FOCUS_AREAS: tuple[str, ...] = (
    "Security properties of systems with multiple interacting AI agents",
    "Attacks and failures emerging from interacting or coordinating AI agents",
    "Collusion, covert coordination, and agent-to-agent manipulation",
    "Prompt injection, instruction hijacking, or tool misuse in agent systems",
    "Shared-memory, shared-environment, or context-manipulation risks",
    "Trust, governance, assurance, and control boundaries for autonomous agents",
)


FALLBACK_QUERY = (
    '(all:"agent" OR all:"agents" OR all:"agentic" OR all:"multi-agent" OR all:"multi agent") '
    'AND (all:"AI" OR all:"LLM" OR all:"autonomous" OR all:"system")'
)
