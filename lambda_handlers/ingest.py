from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from .runtime_env import hydrate_runtime_env


hydrate_runtime_env(
    (
        "DATABASE_URL",
        "OPENAI_API_KEY",
        "OPENALEX_API_KEY",
        "OPENALEX_EMAIL",
        "CROSSREF_EMAIL",
        "SEMANTIC_SCHOLAR_API_KEY",
    )
)

from services.research_hub import ResearchHubService


def _int_from_event(event: dict[str, Any], key: str, default: int) -> int:
    env_key = key.upper().replace("-", "_")
    value = event.get(key, os.getenv(env_key, default))
    return int(value)


def handler(event: dict[str, Any] | None, _context) -> dict[str, Any]:
    payload = event or {}
    mode = payload.get("mode", os.getenv("INGEST_MODE", "incremental"))
    target_limit = _int_from_event(payload, "target_limit", 250)
    per_topic_limit = _int_from_event(payload, "per_topic_limit", 40)
    years_back = _int_from_event(payload, "years_back", 5)
    overlap_days = _int_from_event(payload, "overlap_days", 3)
    reconcile_lookback_days = _int_from_event(payload, "reconcile_lookback_days", 30)

    result = asyncio.run(
        ResearchHubService().ingest_and_store(
            mode=mode,
            target_limit=target_limit,
            per_topic_limit=per_topic_limit,
            years_back=years_back,
            overlap_days=overlap_days,
            reconcile_lookback_days=reconcile_lookback_days,
        )
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"mode": mode, "result": result}),
    }
