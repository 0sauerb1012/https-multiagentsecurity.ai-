from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "")
    article_limit: int = int(os.getenv("INGESTION_ARTICLE_LIMIT", "25"))

    # TODO: move source toggles and API keys into AWS Secrets Manager references.
    enable_arxiv: bool = os.getenv("ENABLE_ARXIV", "true").lower() == "true"
    enable_crossref: bool = os.getenv("ENABLE_CROSSREF", "true").lower() == "true"
    enable_rss: bool = os.getenv("ENABLE_RSS", "true").lower() == "true"


def get_settings() -> Settings:
    return Settings()
