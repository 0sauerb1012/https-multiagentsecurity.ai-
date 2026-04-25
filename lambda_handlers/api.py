from __future__ import annotations

from mangum import Mangum

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

from main import app


handler = Mangum(app)
