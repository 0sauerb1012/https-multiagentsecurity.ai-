from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    arxiv_base_url: str = os.getenv("ARXIV_BASE_URL", "https://export.arxiv.org/api/query")
    openalex_base_url: str = os.getenv("OPENALEX_BASE_URL", "https://api.openalex.org/works")
    crossref_base_url: str = os.getenv("CROSSREF_BASE_URL", "https://api.crossref.org/works")
    dblp_base_url: str = os.getenv("DBLP_BASE_URL", "https://dblp.org/search/publ/api")
    semantic_scholar_base_url: str = os.getenv(
        "SEMANTIC_SCHOLAR_BASE_URL",
        "https://api.semanticscholar.org/graph/v1/paper/search/bulk",
    )
    openalex_api_key: str | None = os.getenv("OPENALEX_API_KEY")
    openalex_email: str | None = os.getenv("OPENALEX_EMAIL")
    crossref_email: str | None = os.getenv("CROSSREF_EMAIL")
    semantic_scholar_api_key: str | None = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    database_backend: str = os.getenv("DATABASE_BACKEND", "sqlite")
    database_url: str | None = os.getenv("DATABASE_URL")
    database_path: str = os.getenv("DATABASE_PATH", "data/research_hub.db")
    app_name: str = os.getenv("APP_NAME", "arXiv Agent API")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    default_max_results: int = int(os.getenv("DEFAULT_MAX_RESULTS", "10"))
    max_results_limit: int = int(os.getenv("MAX_RESULTS_LIMIT", "25"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_search_model: str = os.getenv("OPENAI_SEARCH_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    openai_review_model: str = os.getenv("OPENAI_REVIEW_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    openai_summary_model: str = os.getenv("OPENAI_SUMMARY_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    paper_text_chunk_chars: int = int(os.getenv("PAPER_TEXT_CHUNK_CHARS", "12000"))
    paper_text_max_chars: int = int(os.getenv("PAPER_TEXT_MAX_CHARS", "120000"))


settings = Settings()
